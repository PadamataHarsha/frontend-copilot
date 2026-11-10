from pydantic import BaseModel


class Section(BaseModel):
    title: str
    components: list[str]


class WireframeResponse(BaseModel):
    screen_name: str
    sections: list[Section]