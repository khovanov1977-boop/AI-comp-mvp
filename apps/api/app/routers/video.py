from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import SessionLocal, get_db
from app.models.message import Message
from app.models.video import VideoJob
from app.providers.video_venice import VeniceVideoError, VeniceVideoProvider
from app.schemas.video import VideoJobRead, VideoQuoteRead, VideoQuoteRequest, VideoRequest
from app.services.video_generation import _poll_video, quote_video, run_video, submit_video
from app.services.beta_limits import PAID_SUBMISSION_LOCK
from app.services.beta_limits import paid_limit_reason

router = APIRouter(prefix="/video", tags=["video"])


def get_video_session_factory():
    return SessionLocal


def to_read(job: VideoJob) -> VideoJobRead:
    return VideoJobRead(id=job.id, mode=job.mode, model=job.model, status=job.status,
                        quote_usd=job.quote_usd, aspect_ratio=job.aspect_ratio or "auto",
                        error=job.error, created_at=job.created_at)


@router.post("/quote", response_model=VideoQuoteRead)
def get_quote(payload: VideoQuoteRequest, db: Session = Depends(get_db)) -> VideoQuoteRead:
    limit_reason = paid_limit_reason(db, "video")
    if limit_reason:
        return VideoQuoteRead(model="", available=False, price_usd=None, unavailable_reason=limit_reason)
    try:
        return quote_video(payload)
    except VeniceVideoError as exc:
        raise HTTPException(503, str(exc)) from exc


@router.post("/{character_id}", response_model=VideoJobRead, status_code=202)
def create_video(character_id: str, payload: VideoRequest, background_tasks: BackgroundTasks,
                 db: Session = Depends(get_db), session_factory=Depends(get_video_session_factory)) -> VideoJobRead:
    with PAID_SUBMISSION_LOCK:
        job, created = submit_video(db, character_id, payload)
    if created:
        background_tasks.add_task(run_video, job.id, session_factory)
    return to_read(job)


@router.get("/{character_id}/{job_id}", response_model=VideoJobRead)
def get_video_job(character_id: str, job_id: str, db: Session = Depends(get_db)) -> VideoJobRead:
    job = db.get(VideoJob, job_id)
    if not job or job.character_id != character_id:
        raise HTTPException(404, "Задание видео не найдено.")
    return to_read(job)


@router.post("/{character_id}/{job_id}/check", response_model=VideoJobRead)
def check_video_job(character_id: str, job_id: str, background_tasks: BackgroundTasks,
                    db: Session = Depends(get_db), session_factory=Depends(get_video_session_factory)) -> VideoJobRead:
    job = db.get(VideoJob, job_id)
    if not job or job.character_id != character_id:
        raise HTTPException(404, "Задание видео не найдено.")
    if not job.queue_id or job.status != "unknown":
        raise HTTPException(409, "У этого задания нет номера для проверки.")
    try:
        provider = VeniceVideoProvider()
    except VeniceVideoError as exc:
        raise HTTPException(503, str(exc)) from exc
    job.status = "processing"
    job.error = ""
    message = db.get(Message, job.assistant_message_id)
    if message:
        message.video_generation_status = "processing"
        message.video_generation_error = ""
        message.content = "Проверяю видео…"
    db.commit()
    background_tasks.add_task(_poll_video, job_id, session_factory, provider)
    return to_read(job)
