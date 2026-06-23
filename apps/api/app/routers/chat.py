from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.character import Character
from app.models.message import Message
from app.schemas.chat import ChatRequest, ChatResponse, CharacterStateRead, MessageRead
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


@router.post("", response_model=ChatResponse)
def post_chat(payload: ChatRequest, db: Session = Depends(get_db)) -> ChatResponse:
    character = db.get(Character, payload.character_id)
    if not character:
        raise HTTPException(status_code=404, detail="Character not found")

    reply, _message = handle_chat_message(db, character, payload.message)
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
