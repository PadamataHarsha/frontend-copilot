from pydantic import BaseModel


class WireframeRequest(BaseModel):
    requirement: str