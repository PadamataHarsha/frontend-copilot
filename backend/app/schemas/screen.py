from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator


ScreenLayoutType = Literal[
    "single-column",
    "sidebar-content",
    "split-panel",
    "dashboard-grid",
]

SectionLayoutType = Literal[
    "single-column",
    "two-column",
    "three-column",
    "grid",
    "stack",
]

ButtonVariant = Literal[
    "primary",
    "secondary",
    "danger",
    "ghost",
]


class ScreenRequest(BaseModel):
    requirement: str = Field(min_length=10, max_length=10_000)

    @field_validator("requirement")
    @classmethod
    def normalize_requirement(cls, value: str) -> str:
        normalized = value.strip()

        if len(normalized) < 10:
            raise ValueError(
                "Requirement must contain at least 10 non-whitespace characters."
            )

        return normalized


class ScreenLayout(BaseModel):
    type: ScreenLayoutType = "single-column"
    max_width: str = Field(default="960px", min_length=2, max_length=20)
    section_gap: str = Field(default="24px", min_length=2, max_length=20)


class ScreenComponent(BaseModel):
    id: str = Field(min_length=1, max_length=80)
    type: str = Field(min_length=1, max_length=50)
    label: str = Field(min_length=1, max_length=120)
    placeholder: str | None = Field(default=None, max_length=160)
    value: str | None = Field(default=None, max_length=160)
    required: bool = False
    options: list[str] = Field(default_factory=list, max_length=20)
    variant: ButtonVariant | None = None

    @field_validator("id", "type", "label")
    @classmethod
    def trim_required_strings(cls, value: str) -> str:
        normalized = value.strip()

        if not normalized:
            raise ValueError("Value must not be blank.")

        return normalized

    @field_validator("placeholder", "value")
    @classmethod
    def trim_optional_strings(cls, value: str | None) -> str | None:
        if value is None:
            return None

        normalized = value.strip()
        return normalized or None

    @field_validator("options")
    @classmethod
    def normalize_options(cls, values: list[str]) -> list[str]:
        normalized: list[str] = []

        for value in values:
            option = value.strip()

            if option and option not in normalized:
                normalized.append(option)

        return normalized


class ScreenSection(BaseModel):
    id: str = Field(min_length=1, max_length=80)
    title: str = Field(min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=300)
    layout: SectionLayoutType = "single-column"
    components: list[ScreenComponent] = Field(
        min_length=1,
        max_length=12,
    )

    @field_validator("id", "title")
    @classmethod
    def trim_required_strings(cls, value: str) -> str:
        normalized = value.strip()

        if not normalized:
            raise ValueError("Value must not be blank.")

        return normalized

    @field_validator("description")
    @classmethod
    def trim_description(cls, value: str | None) -> str | None:
        if value is None:
            return None

        normalized = value.strip()
        return normalized or None

    @model_validator(mode="after")
    def validate_unique_component_ids(self) -> "ScreenSection":
        component_ids = [component.id for component in self.components]

        if len(component_ids) != len(set(component_ids)):
            raise ValueError(
                f"Component IDs must be unique inside section '{self.id}'."
            )

        return self


class DesignTokens(BaseModel):
    primary_color: str = "#2563EB"
    background_color: str = "#F8FAFC"
    surface_color: str = "#FFFFFF"
    text_color: str = "#0F172A"
    muted_text_color: str = "#64748B"
    border_color: str = "#CBD5E1"
    border_radius: str = "12px"
    spacing_unit: str = "8px"
    font_family: str = "Inter, system-ui, sans-serif"

    @field_validator(
        "primary_color",
        "background_color",
        "surface_color",
        "text_color",
        "muted_text_color",
        "border_color",
    )
    @classmethod
    def validate_hex_color(cls, value: str) -> str:
        normalized = value.strip().upper()

        if (
            len(normalized) != 7
            or not normalized.startswith("#")
            or any(
                character not in "0123456789ABCDEF"
                for character in normalized[1:]
            )
        ):
            raise ValueError(
                "Color values must use six-digit hexadecimal format."
            )

        return normalized


class ResponsiveRule(BaseModel):
    breakpoint: str = Field(min_length=2, max_length=20)
    behavior: str = Field(min_length=1, max_length=240)

    @field_validator("breakpoint", "behavior")
    @classmethod
    def trim_strings(cls, value: str) -> str:
        normalized = value.strip()

        if not normalized:
            raise ValueError("Value must not be blank.")

        return normalized


class ScreenResponse(BaseModel):
    screen_name: str = Field(min_length=1, max_length=100)
    screen_description: str = Field(min_length=1, max_length=300)
    layout: ScreenLayout
    sections: list[ScreenSection] = Field(min_length=1, max_length=8)
    design_tokens: DesignTokens
    responsive_rules: list[ResponsiveRule] = Field(
        default_factory=list,
        max_length=5,
    )

    @field_validator("screen_name", "screen_description")
    @classmethod
    def trim_required_strings(cls, value: str) -> str:
        normalized = value.strip()

        if not normalized:
            raise ValueError("Value must not be blank.")

        return normalized

    @model_validator(mode="after")
    def validate_unique_ids(self) -> "ScreenResponse":
        section_ids = [section.id for section in self.sections]

        if len(section_ids) != len(set(section_ids)):
            raise ValueError("Section IDs must be unique.")

        component_ids = [
            component.id
            for section in self.sections
            for component in section.components
        ]

        if len(component_ids) != len(set(component_ids)):
            raise ValueError(
                "Component IDs must be unique across the screen."
            )

        return self