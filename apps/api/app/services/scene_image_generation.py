"""One durable, non-retried Venice edit for an explicit photo request in chat."""

import logging
import re
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config import settings
from app.models.appearance import CharacterAppearance
from app.models.character import Character
from app.models.media_asset import MediaAsset
from app.models.message import Message
from app.models.scene_image import SceneImageJob
from app.providers.image_backend import create_image_provider, image_configuration_error
from app.providers.image_openrouter import ImageProviderError
from app.services.image_generation import GENERATION_SLOTS, IMAGE_COMMIT_LOCK
from app.services.image_storage import ImageStorageError, delete_image, read_image, save_image
from app.services.scene_image_prompt import SceneImagePromptCompiler, SceneImagePromptError
from app.services.scene_service import get_or_create_scene

logger = logging.getLogger(__name__)
PHOTO_INTENT = re.compile(
    r"(?:\b(?:пришли|пришлите|отправь|отправьте|покажи|покажите|сделай|сделайте|сними|"
    r"сфотографируй|сфоткай|скинь|хочу|можно|дай)\b.{0,75}\b(?:фото|фотку|фотографию|снимок|селфи|"
    r"картинку|изображение)\b|\b(?:фото|фотку|фотографию|снимок|селфи)\b.{0,50}\b"
    r"(?:пришли|покажи|сделай|скинь)\b|\b(?:send|show|take|make)\b.{0,60}\b"
    r"(?:photo|picture|selfie|image)\b)",
    re.IGNORECASE | re.DOTALL,
)


def is_photo_request(message: str) -> bool:
    return bool(PHOTO_INTENT.search(message.strip()))


def submit_scene_image(db: Session, character: Character, request: str, request_id: UUID,
                       compiler: SceneImagePromptCompiler | None = None) -> tuple[SceneImageJob, bool]:
    job_id = str(request_id)
    existing = db.get(SceneImageJob, job_id)
    if existing:
        original = db.get(Message, existing.user_message_id)
        if existing.character_id != character.id or not original or original.content != request:
            raise HTTPException(409, "Идентификатор уже используется другим запросом.")
        return existing, False
    error = image_configuration_error(provider_name="venice")
    if error:
        raise HTTPException(503, error)
    if db.scalar(select(SceneImageJob.id).where(SceneImageJob.active_key == character.id)):
        raise HTTPException(409, "Фото для этого персонажа уже создаётся. Дождитесь результата.")
    appearance = db.get(CharacterAppearance, character.id)
    refs = (appearance.published or {}).get("references", {}) if appearance else {}
    selected = refs.get("clothing") or refs.get("body") or refs.get("face")
    if not isinstance(selected, dict) or not isinstance(selected.get("url"), str):
        raise HTTPException(409, "Сначала опубликуйте образ персонажа вне чата.")
    reference_url = selected["url"]
    try:
        read_image(reference_url, character.id)
    except (ImageStorageError, OSError):
        raise HTTPException(409, "Файл опубликованного образа недоступен.") from None
    scene = get_or_create_scene(db, character)
    query = select(Message).where(Message.character_id == character.id, Message.message_type.in_(["text", "voice"]))
    if scene.context_started_at:
        query = query.where(Message.created_at >= scene.context_started_at)
    recent = list(db.scalars(query.order_by(Message.created_at.desc(), Message.id.desc()).limit(32)))
    recent.reverse()
    dialogue = [{"role": item.role, "content": item.content[:1000]} for item in recent if item.content.strip()]
    scene_data = {
        "presence_mode": scene.presence_mode, "location_name": scene.location_name,
        "location_description": scene.location_description,
        "time_description": scene.time_description, "character_position": scene.character_position,
    }
    try:
        compiled = (compiler or SceneImagePromptCompiler()).compile(scene_data, dialogue, request)
    except SceneImagePromptError as exc:
        raise HTTPException(503, str(exc)) from exc
    user_message = Message(character_id=character.id, role="user", content=request)
    assistant_message = Message(character_id=character.id, role="assistant", content="Готовлю фото…",
                                message_type="image", image_generation_status="queued")
    db.add_all([user_message, assistant_message])
    db.flush()
    job = SceneImageJob(id=job_id, character_id=character.id, active_key=character.id,
                        user_message_id=user_message.id, assistant_message_id=assistant_message.id,
                        provider="venice", model=settings.venice_image_edit_model.strip(),
                        reference_url=reference_url, prompt=compiled.prompt, status="queued")
    db.add(job)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        existing = db.get(SceneImageJob, job_id)
        if existing:
            original = db.get(Message, existing.user_message_id)
            if existing.character_id == character.id and original and original.content == request:
                return existing, False
        raise HTTPException(409, "Для персонажа уже выполняется генерация или идентификатор занят.") from None
    return job, True


def _finish(job_id: str, session_factory, status: str, error: str) -> None:
    with session_factory() as db:
        job = db.get(SceneImageJob, job_id)
        if not job or job.status not in {"queued", "running"}:
            return
        message = db.get(Message, job.assistant_message_id)
        if message:
            message.image_generation_status = status
            message.image_generation_error = error
            message.content = "Фото не удалось создать." if status == "failed" else "Результат запроса фото неизвестен. Автоповтор отключён."
        job.status = status
        job.error = error
        job.active_key = None
        db.commit()


def run_scene_image(job_id: str, session_factory, provider=None) -> None:
    with GENERATION_SLOTS:
        with session_factory() as db:
            claimed = db.execute(update(SceneImageJob).where(
                SceneImageJob.id == job_id, SceneImageJob.status == "queued",
            ).values(status="running"))
            if not claimed.rowcount:
                return
            job = db.get(SceneImageJob, job_id)
            message = db.get(Message, job.assistant_message_id)
            if message:
                message.image_generation_status = "running"
            character_id, reference_url, prompt, model = job.character_id, job.reference_url, job.prompt, job.model
            db.commit()
        try:
            reference = read_image(reference_url, character_id)
            result = (provider or create_image_provider("venice")).generate(
                model=model, prompt=prompt, references=[reference])
        except ImageProviderError as exc:
            _finish(job_id, session_factory, "unknown" if exc.unknown_outcome else "failed", str(exc))
            return
        except (ImageStorageError, OSError) as exc:
            _finish(job_id, session_factory, "failed", str(exc))
            return
        except Exception:
            logger.exception("scene_image_request_unknown job_id=%s", job_id)
            _finish(job_id, session_factory, "unknown", "Неожиданный сбой при запросе к Venice; результат неизвестен.")
            return
        url = None
        try:
            with IMAGE_COMMIT_LOCK, session_factory() as db:
                character = db.scalar(select(Character).where(Character.id == character_id).with_for_update())
                job = db.get(SceneImageJob, job_id)
                if not character or not job or job.status != "running":
                    return
                job.cost_usd = str(result.cost_usd) if result.cost_usd is not None else None
                db.commit()
                character = db.scalar(select(Character).where(Character.id == character_id).with_for_update())
                job = db.get(SceneImageJob, job_id)
                if not character or not job or job.status != "running":
                    return
                url = save_image(character_id, result.data)
                db.add(MediaAsset(character_id=character_id, media_type="image", url=url,
                                  provider=f"venice:{model}", prompt=prompt))
                message = db.get(Message, job.assistant_message_id)
                if not message:
                    delete_image(url, character_id)
                    return
                message.image_url = url
                message.content = "Вот фото."
                message.image_generation_status = "completed"
                job.status = "completed"
                job.active_key = None
                db.commit()
        except Exception:
            if url:
                delete_image(url, character_id)
            logger.exception("scene_image_save_failed job_id=%s", job_id)
            _finish(job_id, session_factory, "unknown", "Изображение получено, но сохранить его не удалось.")


def recover_interrupted_scene_images(db: Session) -> None:
    for job in db.scalars(select(SceneImageJob).where(SceneImageJob.status.in_(["queued", "running"]))):
        prior = job.status
        job.status = "unknown" if prior == "running" else "not_started"
        job.active_key = None
        job.error = ("Сервер остановлен во время запроса; результат неизвестен." if prior == "running"
                     else "Запрос не был отправлен до остановки сервера.")
        message = db.get(Message, job.assistant_message_id)
        if message:
            message.image_generation_status = job.status
            message.image_generation_error = job.error
            message.content = "Фото не создано. " + job.error
    db.commit()
