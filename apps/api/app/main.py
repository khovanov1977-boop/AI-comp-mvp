from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.database import Base, engine
from app.models import *  # noqa: F403
from app.routers import characters, chat, debug, health, limits, media, memories, scenes, voice
from app.schema_sync import ensure_dev_schema

app = FastAPI(title="AI Companion API", version="0.0.1")

ALLOWED_ORIGINS = {
    settings.frontend_origin,
    "http://localhost:3000",
    "http://localhost:3001",
    "http://127.0.0.1:3000",
    "http://127.0.0.1:3001",
}


@app.middleware("http")
async def return_json_for_unhandled_errors(request: Request, call_next):
    try:
        return await call_next(request)
    except Exception as exc:
        response = JSONResponse(
            status_code=500,
            content={"detail": {"error": "unhandled_error", "message": str(exc) or exc.__class__.__name__}},
        )
        origin = request.headers.get("origin")
        if origin in ALLOWED_ORIGINS:
            response.headers["Access-Control-Allow-Origin"] = origin
            response.headers["Access-Control-Allow-Credentials"] = "true"
            response.headers["Vary"] = "Origin"
        return response

app.add_middleware(
    CORSMiddleware,
    allow_origins=list(ALLOWED_ORIGINS),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def on_startup() -> None:
    Base.metadata.create_all(bind=engine)
    ensure_dev_schema(engine)


app.include_router(health.router)
app.include_router(characters.router)
app.include_router(chat.router)
app.include_router(debug.router)
app.include_router(media.router)
app.include_router(memories.router)
app.include_router(scenes.router)
app.include_router(voice.router)
app.include_router(limits.router)
