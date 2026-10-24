"""Durable, idempotent video submissions and recoverable Venice retrieval."""

import base64
import logging
import time
from decimal import Decimal, InvalidOperation
from io import BytesIO

from fastapi import HTTPException
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from PIL import Image, ImageOps

from app.config import settings
from app.models.appearance import CharacterAppearance
from app.models.character import Character
from app.models.media_asset import MediaAsset
from app.models.message import Message
from app.models.video import VideoJob
from app.providers.video_venice import QueuedVideo, VeniceVideoError, VeniceVideoProvider
from app.schemas.video import VideoQuoteRequest, VideoQuoteRead, VideoRequest
from app.services.image_storage import ImageStorageError, read_image
from app.services.video_storage import delete_video, save_video
from app.services.beta_limits import paid_limit_reason, reserve_paid_units
from app.services.account_limits import reserve_account_units
from app.services.video_prompt import (
    SceneTranslator, VeniceVideoSceneTranslator, VideoPromptError,
    VideoPromptFormatError, prepare_video_prompt, split_video_prompt,
)

logger = logging.getLogger(__name__)
R2V_MODEL = "wan-3-0-reference-to-video"
I2V_MODEL = R2V_MODEL
POLL_INTERVAL_SECONDS = 5
MAX_POLL_SECONDS = 1800
ASPECT_RATIOS = {"16:9": (16, 9), "9:16": (9, 16), "4:3": (4, 3),
                 "3:4": (3, 4), "1:1": (1, 1), "2:3": (2, 3)}
WAN3_R2V_ASPECT_RATIOS = {"auto": "adaptive", "16:9": "16:9", "9:16": "9:16",
                          "4:3": "4:3", "3:4": "3:4", "1:1": "1:1"}


def _prompts(payload: VideoRequest, translator: SceneTranslator) -> tuple[str, str]:
    user_prompt = payload.prompt.strip()
    english_prompt = prepare_video_prompt(user_prompt, translator)
    if payload.mode == "animate_photo":
        return user_prompt, english_prompt
    provider_prompt = ("The two reference images show the same character: Image 1 shows the face, "
                       "and Image 2 shows the body. " + english_prompt)
    return user_prompt, provider_prompt


def _model_for(mode: str, available: set[str]) -> str | None:
    if mode == "animate_photo":
        requested = settings.venice_video_i2v_model.strip() or I2V_MODEL
        return requested if requested in available else None
    requested = settings.venice_video_r2v_model.strip() or R2V_MODEL
    return requested if requested in available else None


def quote_video(payload: VideoQuoteRequest, provider: VeniceVideoProvider | None = None) -> VideoQuoteRead:
    provider = provider or VeniceVideoProvider()
    model = _model_for(payload.mode, provider.available_models())
    if not model:
        requested = settings.venice_video_i2v_model if payload.mode == "animate_photo" else settings.venice_video_r2v_model
        return VideoQuoteRead(model=requested, available=False, price_usd=None,
                              unavailable_reason="Выбранный способ создания видео сейчас недоступен.")
    if model == R2V_MODEL:
        aspect_ratio = WAN3_R2V_ASPECT_RATIOS.get(payload.aspect_ratio)
        if not aspect_ratio:
            raise HTTPException(422, "Выбранные пропорции кадра не поддерживаются для этого видео.")
        price = provider.quote(model, payload.duration, payload.resolution,
                               aspect_ratio=aspect_ratio, audio=True)
    else:
        if payload.resolution == "480p" or (payload.mode == "reference_video" and payload.duration == "15s"):
            raise HTTPException(422, "Этот способ создания видео не поддерживает выбранные длительность или разрешение.")
        price = provider.quote(model, payload.duration, payload.resolution)
    return VideoQuoteRead(model=model, available=True,
                          price_usd=price)


def _references(db: Session, character_id: str, payload: VideoRequest) -> list[str]:
    if payload.mode == "animate_photo":
        source = db.get(Message, payload.source_message_id) if payload.source_message_id else None
        if not source or source.character_id != character_id or source.role != "assistant" or source.message_type != "image" or source.image_generation_status != "completed" or not source.image_url:
            raise HTTPException(409, "Выберите готовое фото персонажа из этого чата.")
        urls = [source.image_url]
    else:
        appearance = db.get(CharacterAppearance, character_id)
        refs = (appearance.published or {}).get("references", {}) if appearance else {}
        face, body = refs.get("face"), refs.get("body")
        if not isinstance(face, dict) or not isinstance(body, dict) or not face.get("url") or not body.get("url"):
            raise HTTPException(409, "Сначала сохраните выбранные варианты лица и фигуры в мастере внешности.")
        urls = [face["url"], body["url"]]
    try:
        for url in urls:
            read_image(url, character_id)
    except (ImageStorageError, OSError):
        raise HTTPException(409, "Один из референсных файлов недоступен.") from None
    return urls


def submit_video(db: Session, character_id: str, payload: VideoRequest,
                 provider: VeniceVideoProvider | None = None,
                 translator: SceneTranslator | None = None) -> tuple[VideoJob, bool]:
    job_id = str(payload.request_id)
    prompt = payload.prompt.strip()
    aspect_ratio = "" if payload.aspect_ratio == "auto" else payload.aspect_ratio
    existing = db.get(VideoJob, job_id)
    if existing:
        if (existing.character_id != character_id or existing.mode != payload.mode or
            existing.prompt != prompt or existing.source_message_id != payload.source_message_id or
            existing.duration != payload.duration or existing.resolution != payload.resolution or
            existing.aspect_ratio != aspect_ratio):
            raise HTTPException(409, "Идентификатор уже используется другим видео.")
        return existing, False
    try:
        split_video_prompt(prompt)
    except VideoPromptFormatError as exc:
        raise HTTPException(422, str(exc)) from exc
    limit_reason = paid_limit_reason(db, "video")
    if limit_reason:
        raise HTTPException(429, limit_reason)
    if not db.get(Character, character_id):
        raise HTTPException(404, "Персонаж не найден.")
    if db.scalar(select(VideoJob.id).where(VideoJob.active_key == character_id)):
        raise HTTPException(409, "Видео для этого персонажа уже создаётся.")
    refs = _references(db, character_id, payload)
    try:
        quote = quote_video(VideoQuoteRequest(mode=payload.mode, duration=payload.duration,
                                              resolution=payload.resolution,
                                              aspect_ratio=payload.aspect_ratio), provider)
    except VeniceVideoError as exc:
        raise HTTPException(503, str(exc)) from exc
    if not quote.available or not quote.price_usd:
        raise HTTPException(503, quote.unavailable_reason)
    try:
        accepted_price = Decimal(payload.accepted_quote_usd)
    except InvalidOperation:
        raise HTTPException(422, "Недопустимая подтверждённая цена.") from None
    if Decimal(quote.price_usd) != accepted_price:
        raise HTTPException(409, "Цена изменилась. Откройте окно видео и подтвердите новую стоимость.")
    try:
        _, provider_prompt = _prompts(payload, translator or VeniceVideoSceneTranslator())
    except VideoPromptError as exc:
        raise HTTPException(503, str(exc)) from exc
    reserve_account_units(db, db.get(Character, character_id).user_id, "videos_count", 1)
    reserve_paid_units(db, "video", 1)
    user_message = Message(character_id=character_id, role="user", content=prompt)
    assistant_message = Message(character_id=character_id, role="assistant", content="Готовлю видео…",
                                message_type="video", video_generation_status="queued")
    db.add_all([user_message, assistant_message])
    db.flush()
    job = VideoJob(id=job_id, character_id=character_id, active_key=character_id,
                   mode=payload.mode, model=quote.model, user_message_id=user_message.id,
                   assistant_message_id=assistant_message.id, source_message_id=payload.source_message_id,
                   reference_urls=refs, prompt=prompt, provider_prompt=provider_prompt,
                   duration=payload.duration, resolution=payload.resolution,
                   aspect_ratio=aspect_ratio,
                   quote_usd=quote.price_usd, status="queued")
    db.add(job)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        existing = db.get(VideoJob, job_id)
        if existing and existing.character_id == character_id and existing.prompt == prompt:
            return existing, False
        raise HTTPException(409, "Для персонажа уже выполняется генерация или идентификатор занят.") from None
    return job, True


def _set_status(job_id: str, session_factory, status: str, error: str = "") -> None:
    with session_factory() as db:
        job = db.get(VideoJob, job_id)
        if not job or job.status not in {"queued", "sending", "processing", "polling"}:
            return
        job.status = status
        job.error = error
        if status in {"completed", "failed", "unknown", "not_started"}:
            job.active_key = None
        message = db.get(Message, job.assistant_message_id)
        if message:
            message.video_generation_status = status
            message.video_generation_error = error
            if status == "completed":
                message.content = "Вот видео."
            elif status == "unknown":
                message.content = "Результат видео неизвестен. Проверьте задание; автоповтор отключён."
            elif status == "failed":
                message.content = "Видео не удалось создать."
            elif status == "not_started":
                message.content = "Запрос видео не был отправлен."
            else:
                message.content = "Готовлю видео…"
        db.commit()


def _poll_video(job_id: str, session_factory, provider: VeniceVideoProvider) -> None:
    with session_factory() as db:
        claimed = db.execute(update(VideoJob).where(VideoJob.id == job_id, VideoJob.status == "processing")
                             .values(status="polling"))
        db.commit()
        if not claimed.rowcount:
            return
    started = time.monotonic()
    failures = 0
    while time.monotonic() - started < MAX_POLL_SECONDS:
        with session_factory() as db:
            job = db.get(VideoJob, job_id)
            if not job or not job.queue_id or job.status != "polling":
                return
            queued = QueuedVideo(job.model, job.queue_id, job.download_url)
            character_id = job.character_id
        try:
            status, data = provider.retrieve(queued)
            failures = 0
        except VeniceVideoError as exc:
            failures += 1
            if failures >= 6:
                _set_status(job_id, session_factory, "unknown", f"Проверка задания не удалась: {exc}")
                return
            time.sleep(POLL_INTERVAL_SECONDS)
            continue
        if status == "failed":
            _set_status(job_id, session_factory, "failed", "Не удалось создать видео.")
            return
        if status == "completed" and data is not None:
            url = ""
            try:
                url = save_video(character_id, data)
                with session_factory() as db:
                    job = db.get(VideoJob, job_id)
                    if not job or job.status != "polling":
                        delete_video(url, character_id)
                        return
                    message = db.get(Message, job.assistant_message_id)
                    if not message:
                        delete_video(url, character_id)
                        return
                    db.add(MediaAsset(character_id=character_id, media_type="video", url=url,
                                      provider=f"venice:{job.model}", prompt=job.prompt))
                    message.video_url = url
                    message.video_generation_status = "completed"
                    message.video_generation_error = ""
                    message.content = "Вот видео."
                    job.status = "completed"
                    job.error = ""
                    job.active_key = None
                    db.commit()
            except Exception:
                if url:
                    delete_video(url, character_id)
                logger.exception("video_save_failed job_id=%s", job_id)
                _set_status(job_id, session_factory, "unknown", "Видео получено, но сохранить его не удалось.")
                return
            try:
                provider.complete(queued)
            except Exception:
                logger.warning("video_cleanup_failed job_id=%s", job_id)
            return
        time.sleep(POLL_INTERVAL_SECONDS)
    _set_status(job_id, session_factory, "unknown", "Ожидание видео превысило 30 минут. Проверьте задание позже.")


def run_video(job_id: str, session_factory, provider: VeniceVideoProvider | None = None) -> None:
    with session_factory() as db:
        claimed = db.execute(update(VideoJob).where(VideoJob.id == job_id, VideoJob.status == "queued")
                             .values(status="sending"))
        if not claimed.rowcount:
            return
        db.commit()
        job = db.get(VideoJob, job_id)
        urls = job.reference_urls
        payload = {"model": job.model, "prompt": job.provider_prompt,
                   "duration": job.duration, "resolution": job.resolution}
        if job.model == R2V_MODEL:
            payload["aspect_ratio"] = WAN3_R2V_ASPECT_RATIOS[job.aspect_ratio or "auto"]
            payload["audio"] = True
    try:
        if job.model == R2V_MODEL:
            payload["reference_image_urls"] = [_data_url(read_image(url, job.character_id)) for url in urls]
        elif job.mode == "animate_photo":
            payload["image_url"] = _data_url(read_image(urls[0], job.character_id), job.aspect_ratio)
        else:
            payload["reference_image_urls"] = [_data_url(read_image(url, job.character_id)) for url in urls]
        provider = provider or VeniceVideoProvider()
        queued = provider.queue(payload)
    except (ImageStorageError, OSError) as exc:
        _set_status(job_id, session_factory, "failed", str(exc))
        return
    except VeniceVideoError as exc:
        _set_status(job_id, session_factory, "unknown" if exc.unknown_outcome else "failed", str(exc))
        return
    except Exception:
        logger.exception("video_queue_unknown job_id=%s", job_id)
        _set_status(job_id, session_factory, "unknown", "Ошибка при отправке видео; результат неизвестен.")
        return
    with session_factory() as db:
        job = db.get(VideoJob, job_id)
        if not job or job.status != "sending":
            return
        job.model = queued.model
        job.queue_id = queued.queue_id
        job.download_url = queued.download_url
        job.status = "processing"
        message = db.get(Message, job.assistant_message_id)
        if message:
            message.video_generation_status = "processing"
            message.video_job_id = job.id
        db.commit()
    _poll_video(job_id, session_factory, provider)


def recover_interrupted_videos(db: Session) -> list[str]:
    resume = []
    for job in db.scalars(select(VideoJob).where(VideoJob.status.in_(["queued", "sending", "processing", "polling"]))):
        if job.queue_id:
            job.status = "processing"
            resume.append(job.id)
        elif job.status == "queued":
            job.status = "not_started"
            job.error = "Сервер остановился до отправки видео."
            job.active_key = None
        else:
            job.status = "unknown"
            job.error = "Сервер остановился во время отправки; результат неизвестен."
            job.active_key = None
        if not job.queue_id:
            message = db.get(Message, job.assistant_message_id)
            if message:
                message.video_generation_status = job.status
                message.video_generation_error = job.error
                message.content = "Запрос видео не был отправлен." if job.status == "not_started" else "Результат видео неизвестен. Автоповтор отключён."
    db.commit()
    return resume


def _data_url(data: bytes, aspect_ratio: str = "") -> str:
    with Image.open(BytesIO(data)) as source:
        image = source.convert("RGB")
        if aspect_ratio:
            ratio = ASPECT_RATIOS[aspect_ratio]
            image = ImageOps.fit(image, (min(image.width, round(image.height * ratio[0] / ratio[1])),
                                         min(image.height, round(image.width * ratio[1] / ratio[0]))),
                                 method=Image.Resampling.LANCZOS)
        image.thumbnail((2048, 2048))
        output = BytesIO()
        image.save(output, format="JPEG", quality=88, optimize=True)
    return "data:image/jpeg;base64," + base64.b64encode(output.getvalue()).decode("ascii")
