from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routers.wireframe_router import router as wireframe_router
from app.routers.screen_router import router as screen_router

app = FastAPI(title="Frontend Copilot")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(wireframe_router)
app.include_router(screen_router)



@app.get("/")
def health():
    return {
        "status": "healthy",
        "service": "frontend-copilot",
    }