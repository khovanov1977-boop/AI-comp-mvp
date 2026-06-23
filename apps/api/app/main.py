from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.database import Base, engine
from app.models import *  # noqa: F403
from app.routers import characters, chat, health, limits, media, voice

app = FastAPI(title="AI Companion API", version="0.0.1")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_origin, "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def on_startup() -> None:
    Base.metadata.create_all(bind=engine)


app.include_router(health.router)
app.include_router(characters.router)
app.include_router(chat.router)
app.include_router(media.router)
app.include_router(voice.router)
app.include_router(limits.router)
