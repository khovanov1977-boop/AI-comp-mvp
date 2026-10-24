from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.config import settings
from app.database import Base, SessionLocal, engine
from app.models import *  # noqa: F403
from app.routers import appearance, auth, characters, chat, debug, examples, health, limits, media, memories, scenes, users, video, voice
from app.security import SESSION_COOKIE, check_owner, get_session_user
from fastapi import HTTPException
from app.schema_sync import ensure_dev_schema
from app.services.voice_storage import VOICE_STORAGE_ROOT
from app.services.image_storage import IMAGE_STORAGE_ROOT
from app.example_catalog import EXAMPLE_ASSET_ROOT
from app.services.image_generation import recover_interrupted_jobs
from app.services.auth_rate_limit import auth_rate_limiter
from app.services.scene_image_generation import recover_interrupted_scene_images
from app.services.video_generation import recover_interrupted_videos
from app.providers.video_venice import VeniceVideoProvider, VeniceVideoError
from concurrent.futures import ThreadPoolExecutor
import logging

_video_recovery_pool = ThreadPoolExecutor(max_workers=2, thread_name_prefix="video-recovery")
logger = logging.getLogger(__name__)

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
        logger.exception("unhandled_api_error path=%s", request.url.path)
        response = JSONResponse(
            status_code=500,
            content={"detail": {"error": "unhandled_error", "message": (
                "Внутренняя ошибка сервера." if settings.beta_safe_errors else str(exc) or exc.__class__.__name__
            )}},
        )
        origin = request.headers.get("origin")
        if origin in ALLOWED_ORIGINS:
            response.headers["Access-Control-Allow-Origin"] = origin
            response.headers["Access-Control-Allow-Credentials"] = "true"
            response.headers["Vary"] = "Origin"
        return response


@app.middleware("http")
async def limit_public_auth_requests(request: Request, call_next):
    if settings.beta_deployment and request.method == "POST":
        action = request.url.path
        limits = {"/auth/register": (10, 3600), "/auth/login": (20, 900)}
        if action in limits:
            limit, window_seconds = limits[action]
            client_ip = request.client.host if request.client else "unknown"
            retry_after = auth_rate_limiter.retry_after(action, client_ip, limit, window_seconds)
            if retry_after:
                return JSONResponse(
                    status_code=429,
                    content={"detail": "Слишком много попыток. Попробуйте позже."},
                    headers={"Retry-After": str(retry_after)},
                )
    return await call_next(request)


@app.middleware("http")
async def protect_private_routes(request: Request, call_next):
    path = request.url.path
    public_example = request.method in {"GET", "HEAD"} and (
        path == "/examples" or (
            path.startswith("/example-files/") and not path.endswith("/body.png")
        )
    )
    if request.method == "OPTIONS" or path == "/health" or path in {"/auth/register", "/auth/login"} or public_example:
        return await call_next(request)
    if request.method not in {"GET", "HEAD", "OPTIONS"}:
        origin = request.headers.get("origin")
        if origin and origin not in ALLOWED_ORIGINS:
            return JSONResponse(status_code=403, content={"detail": "Недопустимый источник запроса."})
    try:
        with SessionLocal() as db:
            user = get_session_user(db, request.cookies.get(SESSION_COOKIE, ""))
            if not user:
                raise HTTPException(401, "Войдите в аккаунт.")
            request.state.user_id = user.id
            if not path.startswith("/auth/"):
                await check_owner(request, db, user.id)
    except HTTPException as exc:
        return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})
    return await call_next(request)

app.add_middleware(
    CORSMiddleware,
    allow_origins=list(ALLOWED_ORIGINS),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.mount("/voice-files", StaticFiles(directory=VOICE_STORAGE_ROOT, check_dir=False), name="voice-files")
app.mount("/media-files", StaticFiles(directory=IMAGE_STORAGE_ROOT, check_dir=False), name="media-files")
app.mount("/example-files", StaticFiles(directory=EXAMPLE_ASSET_ROOT, check_dir=False), name="example-files")


@app.on_event("startup")
def on_startup() -> None:
    Base.metadata.create_all(bind=engine)
    ensure_dev_schema(engine)
    IMAGE_STORAGE_ROOT.mkdir(parents=True, exist_ok=True)
    with SessionLocal() as db:
        recover_interrupted_jobs(db)
        recover_interrupted_scene_images(db)
        pending_videos = recover_interrupted_videos(db)
    for job_id in pending_videos:
        _video_recovery_pool.submit(_resume_video, job_id)


def _resume_video(job_id: str) -> None:
    from app.services.video_generation import _poll_video, _set_status
    try:
        _poll_video(job_id, SessionLocal, VeniceVideoProvider())
    except VeniceVideoError as exc:
        _set_status(job_id, SessionLocal, "unknown", str(exc))
    except Exception:
        logger.exception("video_recovery_failed job_id=%s", job_id)
        _set_status(job_id, SessionLocal, "unknown", "Не удалось возобновить проверку видео.")


app.include_router(health.router)
app.include_router(auth.router)
app.include_router(characters.router)
app.include_router(examples.router)
app.include_router(appearance.router)
app.include_router(chat.router)
app.include_router(debug.router)
app.include_router(media.router)
app.include_router(video.router)
app.include_router(memories.router)
app.include_router(scenes.router)
app.include_router(users.router)
app.include_router(voice.router)
app.include_router(limits.router)
