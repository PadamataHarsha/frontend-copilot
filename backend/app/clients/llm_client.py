import re
from collections.abc import Mapping
from dataclasses import dataclass
from time import perf_counter

from openai import (
    APIConnectionError,
    APIStatusError,
    APITimeoutError,
    AuthenticationError,
    BadRequestError,
    NotFoundError,
    OpenAI,
    OpenAIError,
    RateLimitError,
)

from app.core.config import LLMConfig, LLMConfigurationError


@dataclass(frozen=True)
class LLMCallResult:
    content: str
    model: str
    duration_seconds: float
    response_character_count: int
    request_id: str | None = None
    provider_status: int | None = None
    retry_after: str | None = None
    finish_reason: str | None = None


class LLMFailure(Exception):
    category = "unexpected_provider_error"
    retryable = False

    def __init__(
        self,
        *,
        exception_class: str,
        model: str,
        duration_seconds: float,
        provider_status: int | None = None,
        request_id: str | None = None,
        retry_after: str | None = None,
        response_character_count: int = 0,
        finish_reason: str | None = None,
        provider_error_type: str | None = None,
        provider_error_code: str | None = None,
        provider_error_indicators: tuple[str, ...] = (),
    ) -> None:
        super().__init__(self.category)
        self.exception_class = exception_class
        self.model = model
        self.duration_seconds = duration_seconds
        self.provider_status = provider_status
        self.request_id = request_id
        self.retry_after = retry_after
        self.response_character_count = response_character_count
        self.finish_reason = finish_reason
        self.provider_error_type = provider_error_type
        self.provider_error_code = provider_error_code
        self.provider_error_indicators = provider_error_indicators


class LLMAuthenticationError(LLMFailure):
    category = "authentication_failure"


class LLMModelNotFoundError(LLMFailure):
    category = "model_not_found"


class LLMRateLimitError(LLMFailure):
    category = "rate_limit"
    retryable = True


class LLMTimeoutError(LLMFailure):
    category = "timeout"
    retryable = True


class LLMConnectionError(LLMFailure):
    category = "connection_error"
    retryable = True


class LLMTemporaryProviderError(LLMFailure):
    category = "temporary_provider_error"
    retryable = True


class LLMBadRequestError(LLMFailure):
    category = "bad_request"


class LLMGenerationBadRequestError(LLMBadRequestError):
    category = "generation_bad_request"
    retryable = True


class LLMUnexpectedProviderError(LLMFailure):
    category = "unexpected_provider_error"


class LLMEmptyResponseError(LLMFailure):
    category = "empty_response"


class LLMMalformedJSONError(LLMFailure):
    category = "malformed_json"


class LLMSchemaInvalidError(LLMFailure):
    category = "schema_invalid_json"


def _failure_metadata(error: Exception, config: LLMConfig, started: float) -> dict:
    response = getattr(error, "response", None)
    headers = getattr(response, "headers", {}) or {}
    return {
        "exception_class": type(error).__name__,
        "model": config.model,
        "duration_seconds": perf_counter() - started,
        "provider_status": getattr(error, "status_code", None),
        "request_id": getattr(error, "request_id", None) or headers.get("x-request-id"),
        "retry_after": headers.get("retry-after"),
    }


def _safe_provider_error_value(value: object) -> str | None:
    if (
        not isinstance(value, str)
        or re.fullmatch(r"[A-Za-z0-9_.-]{1,64}", value) is None
    ):
        return None
    return value


def _has_provider_error_indicator(indicator: str, *values: str | None) -> bool:
    return any(
        value is not None
        and value.lower() in {indicator, f"{indicator}_error"}
        for value in values
    )


def _bad_request_metadata(
    error: BadRequestError, config: LLMConfig, started: float
) -> tuple[dict, bool]:
    body = getattr(error, "body", None)
    if isinstance(body, Mapping):
        details = body.get("error", body)
    else:
        details = None
    if isinstance(details, Mapping):
        error_type = _safe_provider_error_value(details.get("type"))
        error_code = _safe_provider_error_value(details.get("code"))
    else:
        error_type = None
        error_code = None

    indicators = tuple(
        indicator
        for indicator in (
            "failed_generation",
            "json_validate_failed",
            "structured_output",
            "response_format",
            "invalid_request",
        )
        if _has_provider_error_indicator(indicator, error_type, error_code)
    )
    generation_related = (
        "failed_generation" in indicators
        or "json_validate_failed" in indicators
        or {
            "structured_output",
            "response_format",
        }.issubset(indicators)
    )
    metadata = _failure_metadata(error, config, started)
    metadata.update(
        provider_error_type=error_type,
        provider_error_code=error_code,
        provider_error_indicators=indicators,
    )
    return metadata, generation_related


class LLMClient:
    def complete(self, system_prompt: str, requirement: str) -> LLMCallResult:
        config = LLMConfig.from_env()
        started = perf_counter()
        try:
            client = OpenAI(
                api_key=config.api_key,
                base_url=config.base_url,
                timeout=config.timeout_seconds,
            )
            response = client.chat.completions.create(
                model=config.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": requirement},
                ],
                temperature=0.1,
                max_tokens=config.max_output_tokens,
                response_format={"type": "json_object"},
            )
        except AuthenticationError as error:
            raise LLMAuthenticationError(**_failure_metadata(error, config, started)) from error
        except NotFoundError as error:
            raise LLMModelNotFoundError(**_failure_metadata(error, config, started)) from error
        except RateLimitError as error:
            raise LLMRateLimitError(**_failure_metadata(error, config, started)) from error
        except APITimeoutError as error:
            raise LLMTimeoutError(**_failure_metadata(error, config, started)) from error
        except APIConnectionError as error:
            raise LLMConnectionError(**_failure_metadata(error, config, started)) from error
        except BadRequestError as error:
            metadata, generation_related = _bad_request_metadata(
                error, config, started
            )
            error_class = (
                LLMGenerationBadRequestError
                if generation_related
                else LLMBadRequestError
            )
            raise error_class(**metadata) from error
        except APIStatusError as error:
            metadata = _failure_metadata(error, config, started)
            if error.status_code in {500, 502, 503, 504}:
                raise LLMTemporaryProviderError(**metadata) from error
            raise LLMUnexpectedProviderError(**metadata) from error
        except OpenAIError as error:
            raise LLMUnexpectedProviderError(
                **_failure_metadata(error, config, started)
            ) from error
        except (AttributeError, IndexError, TypeError) as error:
            raise LLMUnexpectedProviderError(
                **_failure_metadata(error, config, started)
            ) from error

        try:
            choice = response.choices[0]
            content = choice.message.content
        except (AttributeError, IndexError, KeyError, TypeError):
            choice = None
            content = ""
        if not isinstance(content, str):
            content = ""

        raw_response = getattr(response, "_raw_response", None)
        headers = (
            getattr(response, "headers", None)
            or getattr(raw_response, "headers", None)
            or {}
        )
        finish_reason = None
        if choice is not None:
            try:
                candidate_finish_reason = choice.finish_reason
            except (AttributeError, KeyError, TypeError):
                candidate_finish_reason = None
            if isinstance(candidate_finish_reason, str):
                finish_reason = candidate_finish_reason

        return LLMCallResult(
            content=content,
            model=config.model,
            duration_seconds=perf_counter() - started,
            response_character_count=len(content),
            request_id=getattr(response, "_request_id", None),
            provider_status=(
                getattr(response, "status_code", None)
                or getattr(raw_response, "status_code", None)
            ),
            retry_after=(
                headers.get("retry-after") if isinstance(headers, Mapping) else None
            ),
            finish_reason=finish_reason,
        )