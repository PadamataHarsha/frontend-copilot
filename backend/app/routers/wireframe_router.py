from fastapi import APIRouter

from app.schemas.request_models import WireframeRequest
from app.services.wireframe_service import WireframeService

router = APIRouter(
    prefix="/wireframe",
    tags=["Wireframe"]
)


@router.post("/generate")
def generate_wireframe(request: WireframeRequest):
    return WireframeService.generate(request.requirement)