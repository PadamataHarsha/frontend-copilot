import json
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from fastapi.testclient import TestClient
from openai import BadRequestError

from app.clients.llm_client import (
    LLMAuthenticationError,
    LLMCallResult,
    LLMConnectionError,
    LLMModelNotFoundError,
    LLMRateLimitError,
    LLMTemporaryProviderError,
    LLMTimeoutError,
    LLMUnexpectedProviderError,
)
from app.core.config import LLMConfigurationError
from app.main import app


REQUIREMENT = "Create a patient appointment-booking screen."
VALID_JSON = (
    '{"screen_name":"Patient Appointment Booking","sections":['
    '{"title":"Appointment Selection","components":["Form","Select",'
    '"SearchInput","DatePicker","Select","TextArea"]},'
    '{"title":"Appointment Review","components":["SummaryCard"]},'
    '{"title":"Booking Actions","components":["Button","Button"]},'
    '{"title":"Booking Result","components":["Alert","StatusBadge"]}]}'
)


def result(content: str) -> LLMCallResult:
    return LLMCallResult(
        content=content,
        model="openai/gpt-oss-20b",
        duration_seconds=0.01,
        response_character_count=len(content),
        request_id="req-test",
    )


def failure(error_type, *, status=None, retry_after=None):
    return error_type(
        exception_class="MockProviderError",
        model="openai/gpt-oss-20b",
        duration_seconds=0.01,
        provider_status=status,
        request_id="req-test",
        retry_after=retry_after,
    )


def provider_response(content):
    return SimpleNamespace(
        choices=[
            SimpleNamespace(
                message=SimpleNamespace(content=content),
                finish_reason="stop",
            )
        ],
        _request_id="req-test",
    )


def provider_bad_request(error_type=None, code=None, message="private provider detail"):
    details = {"message": message}
    if error_type is not None:
        details["type"] = error_type
    if code is not None:
        details["code"] = code
    return BadRequestError(
        message,
        response=SimpleNamespace(
            status_code=400,
            headers={"x-request-id": "req-bad-request"},
            request=SimpleNamespace(),
        ),
        body={"error": details},
    )


class WireframeApiTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    @patch(
        "app.services.wireframe_service.LLMClient.complete",
        return_value=result(VALID_JSON),
    )
    def test_direct_successful_generation_preserves_response_contract(self, complete):
        response = self.client.post(
            "/wireframe/generate", json={"requirement": REQUIREMENT}
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["screen_name"], "Patient Appointment Booking")
        self.assertEqual(len(response.json()["sections"]), 4)
        complete.assert_called_once()
        self.assertEqual(complete.call_args.args[1], REQUIREMENT)

    def test_openapi_exposes_direct_post_route(self):
        response = self.client.get("/openapi.json")
        self.assertEqual(response.status_code, 200)
        self.assertIn("post", response.json()["paths"]["/wireframe/generate"])

    @patch("app.services.wireframe_service.time.sleep")
    @patch("app.services.wireframe_service.LLMClient.complete")
    def test_temporary_provider_error_retries_once_then_succeeds(self, complete, sleep):
        complete.side_effect = [
            failure(LLMTemporaryProviderError, status=503, retry_after="1"),
            result(VALID_JSON),
        ]
        response = self.client.post(
            "/wireframe/generate", json={"requirement": REQUIREMENT}
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(complete.call_count, 2)
        sleep.assert_called_once_with(1)

    @patch("app.services.wireframe_service.time.sleep")
    @patch("app.services.wireframe_service.LLMClient.complete")
    def test_out_of_range_retry_after_uses_default_delay(self, complete, sleep):
        complete.side_effect = [
            failure(LLMRateLimitError, status=429, retry_after="30"),
            result(VALID_JSON),
        ]
        response = self.client.post(
            "/wireframe/generate", json={"requirement": REQUIREMENT}
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(complete.call_count, 2)
        sleep.assert_called_once_with(0.5)

    @patch("app.services.wireframe_service.time.sleep")
    @patch("app.services.wireframe_service.LLMClient.complete")
    def test_rate_limit_retries_once_then_succeeds(self, complete, sleep):
        complete.side_effect = [failure(LLMRateLimitError, status=429), result(VALID_JSON)]
        response = self.client.post(
            "/wireframe/generate", json={"requirement": REQUIREMENT}
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(complete.call_count, 2)
        sleep.assert_called_once_with(0.5)

    @patch("app.services.wireframe_service.time.sleep")
    @patch("app.services.wireframe_service.LLMClient.complete")
    def test_timeout_retries_once_then_succeeds(self, complete, sleep):
        complete.side_effect = [failure(LLMTimeoutError), result(VALID_JSON)]
        response = self.client.post(
            "/wireframe/generate", json={"requirement": REQUIREMENT}
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(complete.call_count, 2)
        sleep.assert_called_once_with(0.5)

    @patch("app.services.wireframe_service.time.sleep")
    @patch("app.services.wireframe_service.LLMClient.complete")
    def test_connection_failure_retries_once_then_succeeds(self, complete, sleep):
        complete.side_effect = [failure(LLMConnectionError), result(VALID_JSON)]
        response = self.client.post(
            "/wireframe/generate", json={"requirement": REQUIREMENT}
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(complete.call_count, 2)
        sleep.assert_called_once_with(0.5)

    @patch("app.services.wireframe_service.time.sleep")
    @patch("app.services.wireframe_service.LLMClient.complete")
    def test_temporary_failure_twice_returns_503(self, complete, sleep):
        complete.side_effect = [
            failure(LLMTemporaryProviderError, status=502),
            failure(LLMTemporaryProviderError, status=503),
        ]
        response = self.client.post(
            "/wireframe/generate", json={"requirement": REQUIREMENT}
        )
        self.assertEqual(response.status_code, 503)
        self.assertEqual(complete.call_count, 2)
        self.assertNotIn("MockProviderError", response.text)

    @patch("app.services.wireframe_service.time.sleep")
    @patch("app.services.wireframe_service.LLMClient.complete")
    def test_timeout_twice_returns_504(self, complete, sleep):
        complete.side_effect = [failure(LLMTimeoutError), failure(LLMTimeoutError)]
        response = self.client.post(
            "/wireframe/generate", json={"requirement": REQUIREMENT}
        )
        self.assertEqual(response.status_code, 504)
        self.assertEqual(complete.call_count, 2)

    def test_genuine_bad_request_is_mapped_safely_without_retry(self):
        bad_request = provider_bad_request(
            error_type="invalid_request_error",
            code="invalid_request",
        )
        with (
            patch.dict("os.environ", {"LLM_API_KEY": "test-key"}),
            patch("app.clients.llm_client.OpenAI") as openai_class,
        ):
            create = Mock(side_effect=bad_request)
            openai_class.return_value = SimpleNamespace(
                chat=SimpleNamespace(
                    completions=SimpleNamespace(create=create),
                )
            )
            response = self.client.post(
                "/wireframe/generate", json={"requirement": REQUIREMENT}
            )
        self.assertEqual(response.status_code, 502)
        self.assertEqual(
            response.json()["detail"],
            "The AI provider rejected the generation request.",
        )
        create.assert_called_once()
        self.assertNotIn("private provider detail", response.text)

    def test_unsupported_parameter_bad_request_does_not_retry(self):
        bad_request = provider_bad_request(
            error_type="invalid_request_error",
            code="unsupported_parameter",
        )
        with (
            patch.dict("os.environ", {"LLM_API_KEY": "test-key"}),
            patch("app.clients.llm_client.OpenAI") as openai_class,
        ):
            create = Mock(side_effect=bad_request)
            openai_class.return_value = SimpleNamespace(
                chat=SimpleNamespace(
                    completions=SimpleNamespace(create=create),
                )
            )
            response = self.client.post(
                "/wireframe/generate", json={"requirement": REQUIREMENT}
            )
        self.assertEqual(response.status_code, 502)
        self.assertEqual(
            response.json()["detail"],
            "The AI provider rejected the generation request.",
        )
        create.assert_called_once()

    def test_generation_bad_request_codes_retry_once_then_succeed(self):
        for error_type, code in (
            ("failed_generation", None),
            ("invalid_request_error", "json_validate_failed"),
            ("structured_output", "response_format"),
        ):
            with self.subTest(error_type=error_type, code=code):
                with (
                    patch.dict("os.environ", {"LLM_API_KEY": "test-key"}),
                    patch("app.clients.llm_client.OpenAI") as openai_class,
                    patch("app.services.wireframe_service.time.sleep"),
                ):
                    create = Mock(
                        side_effect=[
                            provider_bad_request(error_type, code),
                            provider_response(VALID_JSON),
                        ]
                    )
                    openai_class.return_value = SimpleNamespace(
                        chat=SimpleNamespace(
                            completions=SimpleNamespace(create=create),
                        )
                    )
                    response = self.client.post(
                        "/wireframe/generate",
                        json={"requirement": REQUIREMENT},
                    )
                self.assertEqual(response.status_code, 200)
                self.assertEqual(create.call_count, 2)

    def test_generation_bad_request_twice_returns_specific_safe_502(self):
        bad_request = provider_bad_request(
            error_type="failed_generation",
            message="do not expose this provider detail",
        )
        with (
            patch.dict("os.environ", {"LLM_API_KEY": "test-key"}),
            patch("app.clients.llm_client.OpenAI") as openai_class,
            patch("app.services.wireframe_service.time.sleep"),
            self.assertLogs("app.services.wireframe_service", level="WARNING") as logs,
        ):
            create = Mock(side_effect=[bad_request, bad_request])
            openai_class.return_value = SimpleNamespace(
                chat=SimpleNamespace(
                    completions=SimpleNamespace(create=create),
                )
            )
            response = self.client.post(
                "/wireframe/generate", json={"requirement": REQUIREMENT}
            )
        self.assertEqual(response.status_code, 502)
        self.assertEqual(
            response.json()["detail"],
            "The AI could not produce a valid structured result.",
        )
        self.assertEqual(create.call_count, 2)
        log_text = "\n".join(logs.output)
        self.assertIn("provider_http_status=400", log_text)
        self.assertIn("provider_error_type=failed_generation", log_text)
        self.assertIn("provider_error_indicators=failed_generation", log_text)
        self.assertNotIn("do not expose this provider detail", log_text)
        self.assertNotIn(REQUIREMENT, log_text)

    def test_unexpected_provider_error_has_specific_safe_detail(self):
        with patch(
            "app.services.wireframe_service.LLMClient.complete",
            side_effect=failure(LLMUnexpectedProviderError, status=400),
        ) as complete:
            response = self.client.post(
                "/wireframe/generate", json={"requirement": REQUIREMENT}
            )
        self.assertEqual(response.status_code, 502)
        self.assertEqual(
            response.json()["detail"],
            "The AI provider returned an unexpected response.",
        )
        complete.assert_called_once()

    def test_json_object_response_is_parsed_and_validated(self):
        with (
            patch.dict(
                "os.environ",
                {
                    "LLM_API_KEY": "test-key",
                    "LLM_BASE_URL": "https://api.groq.com/openai/v1",
                    "LLM_MODEL": "openai/gpt-oss-20b",
                    "LLM_TIMEOUT_SECONDS": "30",
                    "LLM_MAX_OUTPUT_TOKENS": "700",
                },
            ),
            patch("app.clients.llm_client.OpenAI") as openai_class,
        ):
            create = Mock(return_value=provider_response(VALID_JSON))
            openai_class.return_value = SimpleNamespace(
                chat=SimpleNamespace(
                    completions=SimpleNamespace(create=create),
                )
            )
            response = self.client.post(
                "/wireframe/generate", json={"requirement": REQUIREMENT}
            )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json()["screen_name"],
            "Patient Appointment Booking",
        )
        self.assertEqual(create.call_count, 1)

    def test_json_object_repair_path_stays_within_two_provider_calls(self):
        with (
            patch.dict(
                "os.environ",
                {
                    "LLM_API_KEY": "test-key",
                    "LLM_BASE_URL": "https://api.groq.com/openai/v1",
                    "LLM_MODEL": "openai/gpt-oss-20b",
                    "LLM_TIMEOUT_SECONDS": "30",
                    "LLM_MAX_OUTPUT_TOKENS": "700",
                },
            ),
            patch("app.clients.llm_client.OpenAI") as openai_class,
        ):
            create = Mock(
                side_effect=[
                    provider_response(""),
                    provider_response(VALID_JSON),
                ]
            )
            openai_class.return_value = SimpleNamespace(
                chat=SimpleNamespace(
                    completions=SimpleNamespace(create=create),
                )
            )
            response = self.client.post(
                "/wireframe/generate", json={"requirement": REQUIREMENT}
            )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(create.call_count, 2)

    def test_response_shape_failures_are_repaired_and_call_budget_is_bounded(self):
        response_shapes = (
            SimpleNamespace(choices=[]),
            SimpleNamespace(choices=[SimpleNamespace()]),
            SimpleNamespace(
                choices=[SimpleNamespace(message=SimpleNamespace(content=None))]
            ),
            SimpleNamespace(
                choices=[SimpleNamespace(message=SimpleNamespace(content=""))]
            ),
            SimpleNamespace(
                choices=[SimpleNamespace(message=SimpleNamespace(content={"x": 1}))]
            ),
        )
        for invalid_response in response_shapes:
            with self.subTest(response=invalid_response):
                with (
                    patch.dict("os.environ", {"LLM_API_KEY": "test-key"}),
                    patch("app.clients.llm_client.OpenAI") as openai_class,
                ):
                    create = Mock(
                        side_effect=[
                            invalid_response,
                            provider_response(VALID_JSON),
                        ]
                    )
                    openai_class.return_value = SimpleNamespace(
                        chat=SimpleNamespace(
                            completions=SimpleNamespace(create=create),
                        )
                    )
                    response = self.client.post(
                        "/wireframe/generate",
                        json={"requirement": REQUIREMENT},
                    )
                self.assertEqual(response.status_code, 200)
                self.assertEqual(create.call_count, 2)

    def test_invalid_repair_response_returns_invalid_result_502_with_two_calls(self):
        with (
            patch.dict("os.environ", {"LLM_API_KEY": "test-key"}),
            patch("app.clients.llm_client.OpenAI") as openai_class,
        ):
            create = Mock(
                side_effect=[
                    provider_response(""),
                    provider_response("not json"),
                ]
            )
            openai_class.return_value = SimpleNamespace(
                chat=SimpleNamespace(
                    completions=SimpleNamespace(create=create),
                )
            )
            response = self.client.post(
                "/wireframe/generate", json={"requirement": REQUIREMENT}
            )
        self.assertEqual(response.status_code, 502)
        self.assertEqual(response.json()["detail"], "The AI returned an invalid result.")
        self.assertEqual(create.call_count, 2)

    @patch("app.services.wireframe_service.LLMClient.complete")
    def test_malformed_json_is_repaired(self, complete):
        complete.side_effect = [result('{"screen_name":'), result(VALID_JSON)]
        response = self.client.post(
            "/wireframe/generate", json={"requirement": REQUIREMENT}
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(complete.call_count, 2)
        repair_system, repair_user = complete.call_args.args
        self.assertIn("corrected JSON only", repair_system)
        self.assertIn('"sections"', repair_user)
        self.assertIn('{"screen_name":', repair_user)
        self.assertIn("Return corrected JSON only.", repair_user)

    @patch("app.services.wireframe_service.LLMClient.complete")
    def test_schema_invalid_json_is_repaired(self, complete):
        complete.side_effect = [
            result('{"screen_name":12,"sections":[]}'),
            result(VALID_JSON),
        ]
        response = self.client.post(
            "/wireframe/generate", json={"requirement": REQUIREMENT}
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(complete.call_count, 2)

    @patch("app.services.wireframe_service.LLMClient.complete")
    def test_second_invalid_response_returns_502(self, complete):
        complete.side_effect = [result("not json"), result("still not json")]
        response = self.client.post(
            "/wireframe/generate", json={"requirement": REQUIREMENT}
        )
        self.assertEqual(response.status_code, 502)
        self.assertEqual(complete.call_count, 2)
        self.assertNotIn("still not json", response.text)

    @patch("app.services.wireframe_service.time.sleep")
    @patch("app.services.wireframe_service.LLMClient.complete")
    def test_retry_then_invalid_output_does_not_make_repair_call(self, complete, sleep):
        complete.side_effect = [
            failure(LLMTemporaryProviderError, status=503),
            result("not json"),
        ]
        response = self.client.post(
            "/wireframe/generate", json={"requirement": REQUIREMENT}
        )
        self.assertEqual(response.status_code, 502)
        self.assertEqual(complete.call_count, 2)
        sleep.assert_called_once_with(0.5)

    @patch("app.services.wireframe_service.time.sleep")
    @patch("app.services.wireframe_service.LLMClient.complete")
    def test_transient_repair_failure_does_not_retry(self, complete, sleep):
        complete.side_effect = [
            result("not json"),
            failure(LLMTemporaryProviderError, status=503),
        ]
        response = self.client.post(
            "/wireframe/generate", json={"requirement": REQUIREMENT}
        )
        self.assertEqual(response.status_code, 503)
        self.assertEqual(complete.call_count, 2)
        sleep.assert_not_called()

    def test_authentication_and_model_errors_do_not_retry(self):
        errors = (
            (failure(LLMAuthenticationError, status=401), 502),
            (failure(LLMModelNotFoundError, status=404), 502),
        )
        for error, status in errors:
            with self.subTest(error=type(error).__name__):
                with patch(
                    "app.services.wireframe_service.LLMClient.complete",
                    side_effect=error,
                ) as complete:
                    response = self.client.post(
                        "/wireframe/generate", json={"requirement": REQUIREMENT}
                    )
                self.assertEqual(response.status_code, status)
                complete.assert_called_once()
                self.assertNotIn("req-test", response.text)

    @patch("app.services.wireframe_service.LLMClient.complete")
    def test_blank_output_is_rejected_after_one_repair(self, complete):
        complete.side_effect = [result("  "), result("")]
        response = self.client.post(
            "/wireframe/generate", json={"requirement": REQUIREMENT}
        )
        self.assertEqual(response.status_code, 502)
        self.assertEqual(complete.call_count, 2)

    @patch("app.services.wireframe_service.LLMClient.complete")
    def test_repeated_component_types_are_preserved_in_order(self, complete):
        for component_type in ("Button", "DatePicker", "TextInput"):
            with self.subTest(component_type=component_type):
                components = [component_type, component_type]
                complete.return_value = result(
                    json.dumps(
                        {
                            "screen_name": "Booking",
                            "sections": [
                                {"title": "Details", "components": components}
                            ],
                        }
                    )
                )
                response = self.client.post(
                    "/wireframe/generate", json={"requirement": REQUIREMENT}
                )
                self.assertEqual(response.status_code, 200)
                self.assertEqual(
                    response.json()["sections"][0]["components"],
                    components,
                )

    @patch("app.services.wireframe_service.LLMClient.complete")
    def test_blank_component_strings_are_removed(self, complete):
        complete.return_value = result(
            '{"screen_name":"Booking","sections":[{"title":"Details",'
            '"components":[" Button "," ","\\t","CancelButton"]}]}'
        )
        response = self.client.post(
            "/wireframe/generate", json={"requirement": REQUIREMENT}
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json()["sections"][0]["components"],
            ["Button", "Button"],
        )

    @patch("app.services.wireframe_service.LLMClient.complete")
    def test_component_aliases_are_normalized_case_insensitively(self, complete):
        complete.return_value = result(
            '{"screen_name":"Booking","sections":[{"title":"Details",'
            '"components":["emailinput","PHONEINPUT","AddressInput",'
            '"Dropdown","StartDatePicker","EndDatePicker","SubmitButton",'
            '"CancelButton"]},{"title":"Additional Details",'
            '"components":["SuccessMessage","HistoryList","BalanceCard",'
            '"ApprovalCard"]}]}'
        )
        response = self.client.post(
            "/wireframe/generate", json={"requirement": REQUIREMENT}
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json()["sections"][0]["components"],
            [
                "TextInput",
                "TextInput",
                "TextArea",
                "Select",
                "DatePicker",
                "DatePicker",
                "Button",
                "Button",
            ],
        )
        self.assertEqual(
            response.json()["sections"][1]["components"],
            [
                "Alert",
                "List",
                "SummaryCard",
                "Card",
            ],
        )

    @patch("app.services.wireframe_service.LLMClient.complete")
    def test_more_than_ten_components_per_section_is_rejected(self, complete):
        oversized = result(
            json.dumps(
                {
                    "screen_name": "Booking",
                    "sections": [
                        {"title": "Details", "components": ["Button"] * 11}
                    ],
                }
            )
        )
        complete.side_effect = [oversized, oversized]
        response = self.client.post(
            "/wireframe/generate", json={"requirement": REQUIREMENT}
        )
        self.assertEqual(response.status_code, 502)
        self.assertEqual(complete.call_count, 2)

    @patch("app.services.wireframe_service.LLMClient.complete")
    def test_unknown_nonempty_component_is_preserved(self, complete):
        complete.return_value = result(
            '{"screen_name":"Booking","sections":[{"title":"Details",'
            '"components":["CustomWidget"]}]}'
        )
        response = self.client.post(
            "/wireframe/generate", json={"requirement": REQUIREMENT}
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json()["sections"][0]["components"], ["CustomWidget"]
        )

    @patch("app.services.wireframe_service.LLMClient.complete")
    def test_exact_duplicate_sections_are_removed(self, complete):
        complete.return_value = result(
            '{"screen_name":"Booking","sections":['
            '{"title":"Details","components":["Form"]},'
            '{"title":"Details","components":["Form"]}]}'
        )
        response = self.client.post(
            "/wireframe/generate", json={"requirement": REQUIREMENT}
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()["sections"]), 1)

    @patch("app.services.wireframe_service.LLMClient.complete")
    def test_zero_valid_sections_are_rejected(self, complete):
        empty_sections = result('{"screen_name":"Booking","sections":[]}')
        complete.side_effect = [empty_sections, empty_sections]
        response = self.client.post(
            "/wireframe/generate", json={"requirement": REQUIREMENT}
        )
        self.assertEqual(response.status_code, 502)
        self.assertEqual(complete.call_count, 2)

    def test_blank_screen_name_is_rejected(self):
        invalid = result(
            '{"screen_name":"  ","sections":[{"title":"Details",'
            '"components":["Form"]}]}'
        )
        with patch(
            "app.services.wireframe_service.LLMClient.complete",
            side_effect=[invalid, invalid],
        ) as complete:
            response = self.client.post(
                "/wireframe/generate", json={"requirement": REQUIREMENT}
            )
        self.assertEqual(response.status_code, 502)
        self.assertEqual(complete.call_count, 2)

    def test_section_with_no_valid_components_is_rejected(self):
        invalid = result(
            '{"screen_name":"Booking","sections":[{"title":"Details",'
            '"components":[" ","  "]}]}'
        )
        with patch(
            "app.services.wireframe_service.LLMClient.complete",
            side_effect=[invalid, invalid],
        ) as complete:
            response = self.client.post(
                "/wireframe/generate", json={"requirement": REQUIREMENT}
            )
        self.assertEqual(response.status_code, 502)
        self.assertEqual(complete.call_count, 2)

    def test_section_and_component_limits_are_enforced(self):
        too_many_sections = (
            '{"screen_name":"Booking","sections":['
            + ",".join(
                '{"title":"Section%d","components":["Form"]}' % index
                for index in range(9)
            )
            + "]}"
        )
        too_many_components = (
            '{"screen_name":"Booking","sections":[{"title":"Details",'
            '"components":['
            + ",".join('"Component%d"' % index for index in range(11))
            + "]}]}"
        )
        for content in (too_many_sections, too_many_components):
            with self.subTest(content_length=len(content)):
                invalid = result(content)
                with patch(
                    "app.services.wireframe_service.LLMClient.complete",
                    side_effect=[invalid, invalid],
                ) as complete:
                    response = self.client.post(
                        "/wireframe/generate",
                        json={"requirement": REQUIREMENT},
                    )
                self.assertEqual(response.status_code, 502)
                self.assertEqual(complete.call_count, 2)

    @patch("app.services.wireframe_service.LLMClient.complete")
    def test_attempt_logs_are_structured_and_do_not_include_content(self, complete):
        private_requirement = "private requirement text"
        private_output = '{"screen_name":"private output","sections":[]}'
        complete.return_value = result(private_output)
        with self.assertLogs("app.services.wireframe_service", level="INFO") as logs:
            response = self.client.post(
                "/wireframe/generate",
                json={"requirement": private_requirement},
            )
        self.assertEqual(response.status_code, 502)
        log_text = "\n".join(logs.output)
        self.assertIn("attempt_number=1", log_text)
        self.assertIn("purpose=generation", log_text)
        self.assertIn("failure_category=schema_invalid_json", log_text)
        self.assertIn("effective_model=openai/gpt-oss-20b", log_text)
        self.assertIn("response_character_count=", log_text)
        self.assertNotIn(private_requirement, log_text)
        self.assertNotIn(private_output, log_text)

    def test_missing_configuration_returns_500(self):
        with patch(
            "app.services.wireframe_service.LLMClient.complete",
            side_effect=LLMConfigurationError("private configuration"),
        ) as complete:
            response = self.client.post(
                "/wireframe/generate", json={"requirement": REQUIREMENT}
            )
        self.assertEqual(response.status_code, 500)
        complete.assert_called_once()
        self.assertNotIn("private configuration", response.text)

    @patch.dict(
        "os.environ",
        {
            "LLM_API_KEY": "test-key",
            "LLM_BASE_URL": "https://api.groq.com/openai/v1",
            "LLM_MODEL": "openai/gpt-oss-20b",
            "LLM_TIMEOUT_SECONDS": "30",
            "LLM_MAX_OUTPUT_TOKENS": "700",
        },
    )
    @patch("app.clients.llm_client.OpenAI")
    def test_empty_choices_become_repairable_empty_output(self, openai_class):
        from app.clients.llm_client import LLMClient

        completion = SimpleNamespace(choices=[], _request_id="req-empty")
        create = Mock(return_value=completion)
        openai_class.return_value = SimpleNamespace(
            chat=SimpleNamespace(
                completions=SimpleNamespace(create=create),
            )
        )

        response = LLMClient().complete("system", "requirement")

        self.assertEqual(response.content, "")
        self.assertEqual(response.response_character_count, 0)
        self.assertIsNone(response.finish_reason)


class LLMClientTests(unittest.TestCase):
    @patch.dict(
        "os.environ",
        {
            "LLM_API_KEY": "test-key",
            "LLM_BASE_URL": "https://api.groq.com/openai/v1",
            "LLM_MODEL": "openai/gpt-oss-20b",
            "LLM_TIMEOUT_SECONDS": "30",
            "LLM_MAX_OUTPUT_TOKENS": "700",
        },
    )
    @patch("app.clients.llm_client.OpenAI")
    def test_uses_groq_json_object_mode_and_output_limit(self, openai_class):
        from app.clients.llm_client import LLMClient

        completion = SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content="{}"))],
            _request_id="req-test",
        )
        create = Mock(return_value=completion)
        openai_instance = SimpleNamespace(
            chat=SimpleNamespace(
                completions=SimpleNamespace(create=create),
            )
        )
        openai_class.return_value = openai_instance

        response = LLMClient().complete("system", "requirement")

        self.assertEqual(response.content, "{}")
        self.assertEqual(response.model, "openai/gpt-oss-20b")
        self.assertEqual(response.request_id, "req-test")
        response_format = create.call_args.kwargs["response_format"]
        self.assertEqual(response_format, {"type": "json_object"})
        openai_class.assert_called_once_with(
            api_key="test-key",
            base_url="https://api.groq.com/openai/v1",
            timeout=30.0,
        )
        create.assert_called_once_with(
            model="openai/gpt-oss-20b",
            messages=[
                {"role": "system", "content": "system"},
                {"role": "user", "content": "requirement"},
            ],
            temperature=0.1,
            max_tokens=700,
            response_format={"type": "json_object"},
        )


if __name__ == "__main__":
    unittest.main()