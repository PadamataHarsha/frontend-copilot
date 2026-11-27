import json
import logging
import math
import os
import time
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime

from fastapi import HTTPException
from pydantic import ValidationError

from app.clients.llm_client import (
    LLMAuthenticationError,
    LLMBadRequestError,
    LLMCallResult,
    LLMClient,
    LLMConnectionError,
    LLMEmptyResponseError,
    LLMFailure,
    LLMMalformedJSONError,
    LLMModelNotFoundError,
    LLMRateLimitError,
    LLMSchemaInvalidError,
    LLMTemporaryProviderError,
    LLMTimeoutError,
    LLMUnexpectedProviderError,
)
from app.core.config import LLMConfigurationError
from app.prompts.wireframe_prompt import SYSTEM_PROMPT
from app.schemas.wireframe import WireframeResponse

LOGGER = logging.getLogger(__name__)
MAX_PROVIDER_CALLS = 2
MAX_REPAIR_OUTPUT_CHARACTERS = 4000
REPAIR_SYSTEM_PROMPT = (
    "Repair the supplied wireframe data. Return corrected JSON only, with no prose or markdown."
)
REQUIRED_JSON_SCHEMA = json.dumps(
    {
        "type": "object",
        "required": ["screen_name", "sections"],
        "properties": {
            "screen_name": {"type": "string", "minLength": 1},
            "sections": {
                "type": "array",
                "minItems": 1,
                "maxItems": 8,
                "items": {
                    "type": "object",
                    "required": ["title", "components"],
                    "properties": {
                        "title": {"type": "string", "minLength": 1},
                        "components": {
                            "type": "array",
                            "minItems": 1,
                            "maxItems": 10,
                            "items": {"type": "string"},
                        },
                    },
                },
            },
        },
    },
    separators=(",", ":"),
)


def _safe_log_value(value: object | None, limit: int = 128) -> str | None:
    if value is None:
        return None
    return "".join(character for character in str(value) if character.isprintable())[:limit]


def _log_failure(
    category: str,
    exception_class: str | None,
    *,
    attempt_number: int,
    purpose: str,
    model: str,
    duration_seconds: float,
    response_character_count: int,
    provider_status: int | None = None,
    request_id: str | None = None,
    retry_after: str | None = None,
    finish_reason: str | None = None,
    provider_error_type: str | None = None,
    provider_error_code: str | None = None,
    provider_error_indicators: tuple[str, ...] = (),
) -> None:
    log_method = LOGGER.info if category == "none" else LOGGER.warning
    log_method(
        "wireframe_generation_attempt attempt_number=%d purpose=%s "
        "failure_category=%s exception_class=%s "
        "provider_http_status=%s groq_request_id=%s retry_after=%s "
        "provider_error_type=%s provider_error_code=%s "
        "provider_error_indicators=%s "
        "effective_model=%s duration_ms=%.1f response_character_count=%d "
        "finish_reason=%s",
        attempt_number,
        purpose,
        category,
        exception_class,
        provider_status,
        _safe_log_value(request_id),
        _safe_log_value(retry_after, 64),
        _safe_log_value(provider_error_type),
        _safe_log_value(provider_error_code),
        ",".join(provider_error_indicators),
        _safe_log_value(model),
        duration_seconds * 1000,
        response_character_count,
        _safe_log_value(finish_reason),
    )


def _log_success(
    result: LLMCallResult,
    *,
    attempt_number: int,
    purpose: str,
) -> None:
    _log_failure(
        "none",
        None,
        attempt_number=attempt_number,
        purpose=purpose,
        model=result.model,
        duration_seconds=result.duration_seconds,
        response_character_count=result.response_character_count,
        provider_status=result.provider_status,
        request_id=result.request_id,
        retry_after=result.retry_after,
        finish_reason=result.finish_reason,
    )


def _log_llm_failure(
    error: LLMFailure,
    *,
    attempt_number: int,
    purpose: str,
) -> None:
    _log_failure(
        error.category,
        error.exception_class,
        attempt_number=attempt_number,
        purpose=purpose,
        model=error.model,
        duration_seconds=error.duration_seconds,
        response_character_count=error.response_character_count,
        provider_status=error.provider_status,
        request_id=error.request_id,
        retry_after=error.retry_after,
        finish_reason=error.finish_reason,
        provider_error_type=error.provider_error_type,
        provider_error_code=error.provider_error_code,
        provider_error_indicators=error.provider_error_indicators,
    )


class _ProviderCallBudget:
    def __init__(self) -> None:
        self.client = LLMClient()
        self.calls = 0
        self.last_attempt_number = 0
        self.last_purpose = "generation"

    def complete(
        self,
        system_prompt: str,
        user_content: str,
        *,
        purpose: str,
    ) -> LLMCallResult:
        attempt_purpose = purpose
        while self.calls < MAX_PROVIDER_CALLS:
            self.calls += 1
            try:
                result = self.client.complete(system_prompt, user_content)
            except LLMFailure as error:
                _log_llm_failure(
                    error,
                    attempt_number=self.calls,
                    purpose=attempt_purpose,
                )
                if (
                    attempt_purpose == "generation"
                    and error.retryable
                    and self.calls < MAX_PROVIDER_CALLS
                ):
                    time.sleep(WireframeService._retry_delay(error.retry_after))
                    attempt_purpose = "retry"
                    continue
                raise
            _log_success(
                result,
                attempt_number=self.calls,
                purpose=attempt_purpose,
            )
            self.last_attempt_number = self.calls
            self.last_purpose = attempt_purpose
            return result
        raise RuntimeError("Provider call budget exhausted")


class _WireframeNormalizationError(Exception):
    pass


COMPONENT_ALIASES = {
    "emailinput": "TextInput",
    "phoneinput": "TextInput",
    "passwordinput": "TextInput",
    "addressinput": "TextArea",
    "reasoninput": "TextArea",
    "dropdown": "Select",
    "startdatepicker": "DatePicker",
    "enddatepicker": "DatePicker",
    "submitbutton": "Button",
    "cancelbutton": "Button",
    "confirmbutton": "Button",
    "approvebutton": "Button",
    "rejectbutton": "Button",
    "successmessage": "Alert",
    "errormessage": "Alert",
    "validationmessage": "Alert",
    "historylist": "List",
    "balancecard": "SummaryCard",
    "approvalcard": "Card",
}


def _normalize_payload(payload: object) -> object:
    if not isinstance(payload, dict):
        raise _WireframeNormalizationError

    normalized = dict(payload)
    screen_name = normalized.get("screen_name")
    if isinstance(screen_name, str):
        normalized["screen_name"] = screen_name.strip()
        if not normalized["screen_name"]:
            raise _WireframeNormalizationError
    else:
        raise _WireframeNormalizationError

    sections = normalized.get("sections")
    if not isinstance(sections, list):
        raise _WireframeNormalizationError

    normalized_sections = []
    seen_sections = set()
    for raw_section in sections:
        if not isinstance(raw_section, dict):
            normalized_sections.append(raw_section)
            continue

        section = dict(raw_section)
        title = section.get("title")
        if isinstance(title, str):
            section["title"] = title.strip()

        components = section.get("components")
        if isinstance(components, list):
            normalized_components = []
            for component in components:
                if isinstance(component, str):
                    component = component.strip()
                    component = COMPONENT_ALIASES.get(
                        component.casefold(), component
                    )
                    if not component:
                        continue
                normalized_components.append(component)
            section["components"] = normalized_components
            if not normalized_components:
                raise _WireframeNormalizationError
            if len(normalized_components) > 10:
                raise _WireframeNormalizationError

        components = section.get("components")
        section_key = None
        if isinstance(section.get("title"), str) and isinstance(components, list):
            if all(isinstance(component, str) for component in components):
                section_key = (section["title"], tuple(components))
        if section_key is not None:
            if section_key in seen_sections:
                continue
            seen_sections.add(section_key)
        normalized_sections.append(section)

    if not normalized_sections or len(normalized_sections) > 8:
        raise _WireframeNormalizationError
    normalized["sections"] = normalized_sections
    return normalized


def _parse_and_validate(result: LLMCallResult) -> WireframeResponse:
    metadata = {
        "model": result.model,
        "duration_seconds": result.duration_seconds,
        "provider_status": result.provider_status,
        "request_id": result.request_id,
        "retry_after": result.retry_after,
        "response_character_count": result.response_character_count,
        "finish_reason": result.finish_reason,
    }
    if not result.content.strip():
        raise LLMEmptyResponseError(
            exception_class="LLMEmptyResponseError", **metadata
        )

    try:
        payload = json.loads(result.content)
    except json.JSONDecodeError as error:
        raise LLMMalformedJSONError(
            exception_class=type(error).__name__, **metadata
        ) from error

    try:
        normalized = WireframeService._normalize_payload(payload)
        return WireframeResponse.model_validate(normalized)
    except (ValidationError, _WireframeNormalizationError) as error:
        raise LLMSchemaInvalidError(
            exception_class=type(error).__name__, **metadata
        ) from error


def _repair_request(invalid_output: str) -> str:
    return (
        f"Required JSON schema: {REQUIRED_JSON_SCHEMA}\n"
        "Invalid model output (truncated if necessary):\n"
        f"{invalid_output[:MAX_REPAIR_OUTPUT_CHARACTERS]}\n"
        "Return corrected JSON only."
    )


def _http_error(error: LLMFailure) -> HTTPException:
    if isinstance(error, (LLMRateLimitError, LLMConnectionError, LLMTemporaryProviderError)):
        status_code, detail = 503, "The AI service is temporarily unavailable."
    elif isinstance(error, LLMTimeoutError):
        status_code, detail = 504, "The AI response timed out."
    elif isinstance(error, LLMAuthenticationError):
        status_code, detail = 502, "The AI provider rejected the request."
    elif isinstance(error, LLMModelNotFoundError):
        status_code, detail = 502, "The requested AI model is unavailable."
    elif isinstance(error, LLMBadRequestError):
        if error.retryable:
            status_code, detail = (
                502,
                "The AI could not produce a valid structured result.",
            )
        else:
            status_code, detail = (
                502,
                "The AI provider rejected the generation request.",
            )
    elif isinstance(error, LLMUnexpectedProviderError):
        status_code, detail = (
            502,
            "The AI provider returned an unexpected response.",
        )
    elif isinstance(
        error,
        (LLMEmptyResponseError, LLMMalformedJSONError, LLMSchemaInvalidError),
    ):
        status_code, detail = 502, "The AI returned an invalid result."
    else:
        status_code, detail = 502, "Wireframe generation failed at the provider."
    return HTTPException(status_code=status_code, detail=detail)

class WireframeService:
    @staticmethod
    def _retry_delay(retry_after: str | None) -> float:
        if retry_after:
            try:
                delay = float(retry_after)
            except ValueError:
                try:
                    retry_time = parsedate_to_datetime(retry_after)
                    if retry_time.tzinfo is None:
                        retry_time = retry_time.replace(tzinfo=timezone.utc)
                    delay = (retry_time - datetime.now(timezone.utc)).total_seconds()
                except (IndexError, TypeError, ValueError, OverflowError):
                    delay = 0.5
            if not math.isfinite(delay):
                return 0.5
            return delay if 0 <= delay <= 5 else 0.5
        return 0.5

    @staticmethod
    def _normalize_payload(payload: object) -> object:
        return _normalize_payload(payload)

    @staticmethod
    def generate(requirement: str) -> WireframeResponse:
        budget = _ProviderCallBudget()
        try:
            result = budget.complete(
                SYSTEM_PROMPT,
                requirement,
                purpose="generation",
            )
        except LLMConfigurationError as error:
            _log_failure(
                "missing_configuration",
                type(error).__name__,
                attempt_number=max(budget.calls, 1),
                purpose="generation",
                model=os.getenv("LLM_MODEL", "openai/gpt-oss-20b"),
                duration_seconds=0,
                response_character_count=0,
            )
            raise HTTPException(
                status_code=500,
                detail="Wireframe generation is not configured.",
            ) from error
        except LLMFailure as error:
            raise _http_error(error) from error

        first_output_error = None
        try:
            return _parse_and_validate(result)
        except LLMFailure as error:
            first_output_error = error
            _log_llm_failure(
                error,
                attempt_number=budget.last_attempt_number,
                purpose=budget.last_purpose,
            )

        if budget.calls >= MAX_PROVIDER_CALLS:
            raise _http_error(first_output_error)

        try:
            repaired = budget.complete(
                REPAIR_SYSTEM_PROMPT,
                _repair_request(result.content),
                purpose="repair",
            )
        except LLMConfigurationError as error:
            _log_failure(
                "missing_configuration",
                type(error).__name__,
                attempt_number=max(budget.calls, 1),
                purpose="repair",
                model=os.getenv("LLM_MODEL", "openai/gpt-oss-20b"),
                duration_seconds=0,
                response_character_count=0,
            )
            raise HTTPException(
                status_code=500,
                detail="Wireframe generation is not configured.",
            ) from error
        except LLMFailure as provider_error:
            raise _http_error(provider_error) from provider_error

        try:
            return _parse_and_validate(repaired)
        except LLMFailure as repair_error:
            _log_llm_failure(
                repair_error,
                attempt_number=budget.last_attempt_number,
                purpose=budget.last_purpose,
            )
            raise _http_error(repair_error) from repair_error