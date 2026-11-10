from fastapi import FastAPI

from app.routers.wireframe_router import router as wireframe_router

app = FastAPI(
    title="Frontend Copilot"
)

app.include_router(wireframe_router)


@app.get("/")
def health():
    return {
        "status": "healthy",
        "service": "frontend-copilot"
    }