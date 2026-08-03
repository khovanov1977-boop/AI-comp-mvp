from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.character import Character
from app.models.message import Message
from app.providers.llm_openai_compatible import LLMConfigurationError, LLMProviderError
from app.schemas.chat import ChatRequest, ChatResponse, CharacterStateRead, CompanionContextRead, MessageRead
from app.services.memory_service import list_character_memories
from app.services.orchestrator import handle_chat_message

router = APIRouter(prefix="/chat", tags=["chat"])


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
    return CompanionContextRead(
        character_state=CharacterStateRead(
            mood=state.mood,
            trust_level=state.trust_level,
            attachment_level=state.attachment_level,
            energy_level=state.energy_level,
        ),
        memories=list_character_memories(db, character_id),
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
