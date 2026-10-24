from datetime import datetime, timezone

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.database import SessionLocal, get_db
from app.models.character import Character
from app.models.memory import Memory
from app.models.message import Message
from app.models.scene_image import SceneImageJob
from app.models.video import VideoJob
from app.providers.llm_openai_compatible import LLMConfigurationError, LLMProviderError
from app.providers.tts_openrouter import TTSConfigurationError, TTSProviderError
from app.schemas.chat import (
    ChatExportRead,
    ChatHistoryClearRead,
    ChatRequest,
    ChatResponse,
    ChatRetryRequest,
    CharacterStateRead,
    CompanionContextRead,
    MemoryMetaRead,
    MessageRead,
    SceneContextRead,
    ScenarioIdeasRead,
    UserContextRead,
)
from app.routers.characters import to_character_read
from app.schemas.llm import CharacterReply
from app.services.memory_service import get_memory_counts_by_category, list_character_memories
from app.services.orchestrator import handle_chat_message, retry_last_user_message
from app.services.scene_image_generation import is_photo_request, run_scene_image, submit_scene_image
from app.services.beta_limits import PAID_SUBMISSION_LOCK
from app.services.public_errors import unexpected_error_message
from app.services.image_generation import IMAGE_COMMIT_LOCK
from app.services.scene_service import get_or_create_scene
from app.services.scenario_ideas import ScenarioIdeasError, generate_scenario_ideas
from app.services.voice_intent import should_generate_voice_reply
from app.services.voice_service import attach_prepared_character_voice, prepare_character_voice
from app.services.voice_storage import VoiceStorageError, delete_voice_file

router = APIRouter(prefix="/chat", tags=["chat"])
MEMORY_CONTEXT_LIMIT = 8


def get_scene_image_session_factory():
    return SessionLocal


def attach_requested_voice(
    db: Session,
    character: Character,
    message: Message,
    reply_plan: CharacterReply,
) -> tuple[str, str]:
    try:
        prepare_character_voice(character, message, reply_plan)
        db.add(message)
        db.commit()
        attach_prepared_character_voice(message)
        db.add(message)
        db.commit()
        return "", ""
    except (TTSConfigurationError, TTSProviderError, VoiceStorageError) as exc:
        db.rollback()
        db.refresh(message)
        message.voice_generation_status = "failed"
        message.voice_generation_error = str(exc)
        db.add(message)
        db.commit()
        return (
            "voice_generation_error",
            f"Text reply was saved, but voice generation failed: {exc}",
        )
    except Exception as exc:
        db.rollback()
        db.refresh(message)
        message.voice_generation_status = "failed"
        message.voice_generation_error = unexpected_error_message(exc)
        db.add(message)
        db.commit()
        return (
            "voice_generation_error",
            "Text reply was saved, but voice generation failed: "
            f"{unexpected_error_message(exc)}",
        )


def to_scene_context_read(scene) -> SceneContextRead:
    return SceneContextRead(
        character_id=scene.character_id,
        presence_mode=scene.presence_mode,
        location_name=scene.location_name,
        location_description=scene.location_description,
        time_description=scene.time_description,
        user_position=scene.user_position,
        character_position=scene.character_position,
        context_started_at=scene.context_started_at,
    )


@router.get("/{character_id}/export", response_model=ChatExportRead)
def export_chat(character_id: str, db: Session = Depends(get_db)) -> ChatExportRead:
    character = db.get(Character, character_id)
    if not character:
        raise HTTPException(status_code=404, detail="Character not found")

    scene = get_or_create_scene(db, character)
    memories = list(
        db.scalars(
            select(Memory)
            .where(Memory.character_id == character_id)
            .order_by(Memory.created_at.asc())
        )
    )
    messages = list(
        db.scalars(
            select(Message)
            .where(Message.character_id == character_id)
            .order_by(Message.created_at.asc())
        )
    )
    return ChatExportRead(
        exported_at=datetime.now(timezone.utc),
        character=to_character_read(character),
        scene_context=to_scene_context_read(scene),
        memories=memories,
        messages=messages,
    )


@router.get("/{character_id}", response_model=list[MessageRead])
def get_chat_history(character_id: str, db: Session = Depends(get_db)) -> list[MessageRead]:
    character = db.get(Character, character_id)
    if not character:
        raise HTTPException(status_code=404, detail="Character not found")

    return list(
        db.scalars(
            select(Message)
            .where(Message.character_id == character_id)
            .order_by(Message.created_at.asc())
        )
    )


@router.delete("/{character_id}", response_model=ChatHistoryClearRead)
def clear_chat_history(character_id: str, db: Session = Depends(get_db)) -> ChatHistoryClearRead:
    character = db.get(Character, character_id)
    if not character:
        raise HTTPException(status_code=404, detail="Character not found")

    audio_urls = db.scalars(
        select(Message.audio_url).where(
            Message.character_id == character_id,
            Message.audio_url != "",
        )
    ).all()
    for audio_url in audio_urls:
        delete_voice_file(audio_url)

    with IMAGE_COMMIT_LOCK:
        db.execute(delete(SceneImageJob).where(SceneImageJob.character_id == character_id))
        db.execute(delete(VideoJob).where(VideoJob.character_id == character_id))
        delete_result = db.execute(delete(Message).where(Message.character_id == character_id))
        db.commit()
    preserved_memories = db.scalar(
        select(func.count()).select_from(Memory).where(Memory.character_id == character_id)
    )
    return ChatHistoryClearRead(
        status="cleared",
        character_id=character_id,
        deleted_messages=max(delete_result.rowcount or 0, 0),
        preserved_memories=preserved_memories or 0,
    )


@router.get("/{character_id}/context", response_model=CompanionContextRead)
def get_companion_context(character_id: str, db: Session = Depends(get_db)) -> CompanionContextRead:
    character = db.get(Character, character_id)
    if not character:
        raise HTTPException(status_code=404, detail="Character not found")

    state = character.state
    scene = get_or_create_scene(db, character)
    memories = list_character_memories(db, character_id, limit=MEMORY_CONTEXT_LIMIT)
    counts_by_category = get_memory_counts_by_category(db, character_id)
    total_count = sum(counts_by_category.values())
    return CompanionContextRead(
        character_state=CharacterStateRead(
            mood=state.mood,
            trust_level=state.trust_level,
            attachment_level=state.attachment_level,
            energy_level=state.energy_level,
        ),
        user_context=UserContextRead(
            display_name=character.user.display_name if character.user else "",
            formal_name=character.user.formal_name if character.user else "",
            preferred_name=character.user.preferred_name if character.user else "",
            casual_name=character.user.casual_name if character.user else "",
            vocative_name=character.user.vocative_name if character.user else "",
            age=character.user.age if character.user else None,
            city=character.user.city if character.user else "",
            country=character.user.country if character.user else "",
            timezone=character.user.timezone if character.user else "Europe/Moscow",
            language=character.user.language if character.user else "ru",
        ),
        scene_context=to_scene_context_read(scene),
        memory_meta=MemoryMetaRead(
            total_count=total_count,
            visible_count=len(memories),
            visible_limit=MEMORY_CONTEXT_LIMIT,
            counts_by_category=counts_by_category,
            extraction_mode="rule_based",
            note="Automatic memory is extracted by local rules from user messages. The panel shows the current working set sorted by importance and recency.",
        ),
        memories=memories,
    )


@router.post("/{character_id}/ideas", response_model=ScenarioIdeasRead)
def create_scenario_ideas(character_id: str, db: Session = Depends(get_db)) -> ScenarioIdeasRead:
    character = db.get(Character, character_id)
    if not character:
        raise HTTPException(404, "Персонаж не найден.")
    scene = get_or_create_scene(db, character)
    try:
        return generate_scenario_ideas(character, scene)
    except ScenarioIdeasError as exc:
        raise HTTPException(503, str(exc)) from exc


@router.post("", response_model=ChatResponse)
def post_chat(payload: ChatRequest, background_tasks: BackgroundTasks, db: Session = Depends(get_db),
              image_session_factory=Depends(get_scene_image_session_factory)) -> ChatResponse:
    character = db.get(Character, payload.character_id)
    if not character:
        raise HTTPException(status_code=404, detail="Character not found")

    if is_photo_request(payload.message):
        if payload.request_id is None:
            raise HTTPException(422, "Для запроса фото нужен идентификатор request_id.")
        with PAID_SUBMISSION_LOCK:
            job, created = submit_scene_image(db, character, payload.message, payload.request_id)
        if created:
            background_tasks.add_task(run_scene_image, job.id, image_session_factory)
        return ChatResponse(
            reply="Готовлю фото…" if job.status in {"queued", "running"} else "Статус фото обновлён.",
            character_state=CharacterStateRead(
                mood=character.state.mood, trust_level=character.state.trust_level,
                attachment_level=character.state.attachment_level, energy_level=character.state.energy_level,
            ),
        )

    try:
        reply, assistant_message, reply_plan = handle_chat_message(db, character, payload.message)
    except HTTPException:
        db.rollback()
        raise
    except LLMConfigurationError as exc:
        db.rollback()
        raise HTTPException(
            status_code=503,
            detail={"error": "llm_configuration_error", "message": str(exc)},
        ) from exc
    except LLMProviderError as exc:
        db.rollback()
        raise HTTPException(
            status_code=503,
            detail={"error": "llm_provider_error", "message": str(exc)},
        ) from exc
    except Exception as exc:
        db.rollback()
        raise HTTPException(
            status_code=503,
            detail={"error": "chat_error", "message": unexpected_error_message(exc)},
        ) from exc

    error_type = ""
    error_message = ""
    if should_generate_voice_reply(payload.message):
        error_type, error_message = attach_requested_voice(
            db,
            character,
            assistant_message,
            reply_plan,
        )

    state = character.state
    return ChatResponse(
        reply=reply,
        character_state=CharacterStateRead(
            mood=state.mood,
            trust_level=state.trust_level,
            attachment_level=state.attachment_level,
            energy_level=state.energy_level,
        ),
        error_type=error_type,
        error_message=error_message,
    )


@router.post("/retry", response_model=ChatResponse)
def retry_chat(payload: ChatRetryRequest, db: Session = Depends(get_db)) -> ChatResponse:
    character = db.get(Character, payload.character_id)
    if not character:
        raise HTTPException(status_code=404, detail="Character not found")

    last_message = db.scalar(
        select(Message)
        .where(Message.character_id == character.id)
        .order_by(Message.created_at.desc())
        .limit(1)
    )
    voice_requested = bool(
        last_message
        and last_message.role == "user"
        and should_generate_voice_reply(last_message.content)
    )

    try:
        reply, assistant_message, reply_plan = retry_last_user_message(db, character)
    except HTTPException:
        db.rollback()
        raise
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except LLMConfigurationError as exc:
        db.rollback()
        raise HTTPException(
            status_code=503,
            detail={"error": "llm_configuration_error", "message": str(exc)},
        ) from exc
    except LLMProviderError as exc:
        db.rollback()
        raise HTTPException(
            status_code=503,
            detail={"error": "llm_provider_error", "message": str(exc)},
        ) from exc
    except Exception as exc:
        db.rollback()
        raise HTTPException(
            status_code=503,
            detail={"error": "chat_error", "message": unexpected_error_message(exc)},
        ) from exc

    error_type = ""
    error_message = ""
    if voice_requested:
        error_type, error_message = attach_requested_voice(
            db,
            character,
            assistant_message,
            reply_plan,
        )

    state = character.state
    return ChatResponse(
        reply=reply,
        character_state=CharacterStateRead(
            mood=state.mood,
            trust_level=state.trust_level,
            attachment_level=state.attachment_level,
            energy_level=state.energy_level,
        ),
        error_type=error_type,
        error_message=error_message,
    )
