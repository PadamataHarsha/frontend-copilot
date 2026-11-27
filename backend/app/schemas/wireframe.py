from pydantic import BaseModel, Field


class Section(BaseModel):
    title: str = Field(min_length=1)
    components: list[str] = Field(min_length=1, max_length=10)


class WireframeResponse(BaseModel):
    screen_name: str = Field(min_length=1)
    sections: list[Section] = Field(min_length=1, max_length=8)