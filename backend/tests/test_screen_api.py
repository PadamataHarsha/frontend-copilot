import unittest

from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.main import app
from app.schemas.screen import (
    DesignTokens,
    ScreenComponent,
    ScreenRequest,
    ScreenResponse,
    ScreenSection,
)


class ScreenSchemaTests(unittest.TestCase):
    def test_requirement_is_trimmed(self) -> None:
        request = ScreenRequest(
            requirement="  Create a fund-transfer screen.  "
        )

        self.assertEqual(
            request.requirement,
            "Create a fund-transfer screen.",
        )

    def test_short_requirement_is_rejected(self) -> None:
        with self.assertRaises(ValidationError):
            ScreenRequest(requirement="Too short")

    def test_invalid_hex_color_is_rejected(self) -> None:
        with self.assertRaises(ValidationError):
            DesignTokens(primary_color="blue")

    def test_duplicate_component_ids_are_rejected(self) -> None:
        with self.assertRaises(ValidationError):
            ScreenSection(
                id="details",
                title="Details",
                components=[
                    ScreenComponent(
                        id="amount",
                        type="NumberInput",
                        label="Amount",
                    ),
                    ScreenComponent(
                        id="amount",
                        type="TextInput",
                        label="Remarks",
                    ),
                ],
            )

    def test_duplicate_section_ids_are_rejected(self) -> None:
        section = ScreenSection(
            id="details",
            title="Details",
            components=[
                ScreenComponent(
                    id="amount",
                    type="NumberInput",
                    label="Amount",
                )
            ],
        )

        with self.assertRaises(ValidationError):
            ScreenResponse(
                screen_name="Transfer",
                screen_description="Transfer funds.",
                layout={
                    "type": "single-column",
                    "max_width": "960px",
                    "section_gap": "24px",
                },
                sections=[section, section],
                design_tokens=DesignTokens(),
            )


class ScreenApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.client = TestClient(app)

    def test_uc02_route_is_in_openapi(self) -> None:
        paths = self.client.get("/openapi.json").json()["paths"]

        self.assertIn(
            "/api/v1/use-cases/uc02/generate",
            paths,
        )

    def test_mock_screen_generation(self) -> None:
        response = self.client.post(
            "/api/v1/use-cases/uc02/generate",
            json={
                "requirement": (
                    "Create a domestic fund-transfer screen "
                    "with review and confirmation."
                )
            },
        )

        self.assertEqual(response.status_code, 200)

        payload = response.json()

        self.assertEqual(
            payload["screen_name"],
            "Domestic Fund Transfer",
        )
        self.assertGreaterEqual(len(payload["sections"]), 1)
        self.assertIn("design_tokens", payload)
        self.assertIn("responsive_rules", payload)

    def test_invalid_requirement_returns_422(self) -> None:
        response = self.client.post(
            "/api/v1/use-cases/uc02/generate",
            json={"requirement": "short"},
        )

        self.assertEqual(response.status_code, 422)


if __name__ == "__main__":
    unittest.main()