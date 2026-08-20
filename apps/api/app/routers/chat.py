from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.character import Character
from app.models.message import Message
from app.providers.llm_openai_compatible import LLMConfigurationError, LLMProviderError
from app.schemas.chat import (
    ChatRequest,
    ChatResponse,
    ChatRetryRequest,
    CharacterStateRead,
    CompanionContextRead,
    MemoryMetaRead,
    MessageRead,
    SceneContextRead,
    UserContextRead,
)
from app.services.memory_service import get_memory_counts_by_category, list_character_memories
from app.services.orchestrator import handle_chat_message, retry_last_user_message
from app.services.scene_service import get_or_create_scene

router = APIRouter(prefix="/chat", tags=["chat"])
MEMORY_CONTEXT_LIMIT = 8


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
            city=character.user.city if character.user else "",
            country=character.user.country if character.user else "",
            timezone=character.user.timezone if character.user else "Europe/Moscow",
            language=character.user.language if character.user else "ru",
        ),
        scene_context=SceneContextRead(
            character_id=scene.character_id,
            presence_mode=scene.presence_mode,
            location_name=scene.location_name,
            location_description=scene.location_description,
            user_position=scene.user_position,
            character_position=scene.character_position,
        ),
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


@router.post("", response_model=ChatResponse)
def post_chat(payload: ChatRequest, db: Session = Depends(get_db)) -> ChatResponse:
    character = db.get(Character, payload.character_id)
    if not character:
        raise HTTPException(status_code=404, detail="Character not found")

    try:
        reply, _message = handle_chat_message(db, character, payload.message)
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
            detail={"error": "chat_error", "message": str(exc) or exc.__class__.__name__},
        ) from exc

    state = character.state
    return ChatResponse(
        reply=reply,
        character_state=CharacterStateRead(
            mood=state.mood,
            trust_level=state.trust_level,
            attachment_level=state.attachment_level,
            energy_level=state.energy_level,
        ),
    )


@router.post("/retry", response_model=ChatResponse)
def retry_chat(payload: ChatRetryRequest, db: Session = Depends(get_db)) -> ChatResponse:
    character = db.get(Character, payload.character_id)
    if not character:
        raise HTTPException(status_code=404, detail="Character not found")

    try:
        reply, _message = retry_last_user_message(db, character)
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
            detail={"error": "chat_error", "message": str(exc) or exc.__class__.__name__},
        ) from exc

    state = character.state
    return ChatResponse(
        reply=reply,
        character_state=CharacterStateRead(
            mood=state.mood,
            trust_level=state.trust_level,
            attachment_level=state.attachment_level,
            energy_level=state.energy_level,
        ),
    )
