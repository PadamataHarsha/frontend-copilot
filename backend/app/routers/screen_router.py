from fastapi import APIRouter

from app.schemas.screen import (
    ScreenRequest,
    ScreenResponse,
)
from app.services.screen_service import ScreenService


router = APIRouter(
    prefix="/api/v1/use-cases/uc02",
    tags=["UC02 - Requirement to Screen"],
)


@router.post(
    "/generate",
    response_model=ScreenResponse,
    response_model_exclude_none=True,
)
def generate_screen(request: ScreenRequest) -> ScreenResponse:
    return ScreenService.generate(request.requirement)