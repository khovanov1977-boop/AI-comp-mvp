from sqlalchemy.orm import Session
from sqlalchemy import select

from app.models.character import Character
from app.models.message import Message
from app.providers.llm_factory import get_llm_provider
from app.services.character_engine import update_state_after_message
from app.services.orchestrator_context import build_orchestrator_context
from app.services.memory_service import remember_user_message
from app.services.response_sanitizer import sanitize_assistant_reply


def generate_assistant_reply(db: Session, character: Character, user_message: str) -> tuple[str, Message]:
    context = build_orchestrator_context(db, character, user_message, recent_message_limit=8)
    reply = sanitize_assistant_reply(get_llm_provider().generate_reply(context))
    outbound = Message(character_id=character.id, role="assistant", content=reply, message_type="text")
    db.add(outbound)

    update_state_after_message(character, user_message)
    db.commit()
    db.refresh(outbound)
    return reply, outbound


def handle_chat_message(db: Session, character: Character, user_message: str) -> tuple[str, Message]:
    inbound = Message(character_id=character.id, role="user", content=user_message, message_type="text")
    db.add(inbound)
    remember_user_message(db, character.id, user_message)
    db.commit()
    db.refresh(character)

    return generate_assistant_reply(db, character, user_message)


def retry_last_user_message(db: Session, character: Character) -> tuple[str, Message]:
    last_message = db.scalar(
        select(Message)
        .where(Message.character_id == character.id)
        .order_by(Message.created_at.desc())
        .limit(1)
    )
    if not last_message or last_message.role != "user":
        raise ValueError("No failed user message to retry")

    return generate_assistant_reply(db, character, last_message.content)
