from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.character import Character
from app.models.message import Message
from app.providers.llm_mock import generate_reply
from app.services.character_engine import update_state_after_message
from app.services.orchestrator_context import build_orchestrator_context
from app.services.memory_service import remember_user_message


def handle_chat_message(db: Session, character: Character, user_message: str) -> tuple[str, Message]:
    inbound = Message(character_id=character.id, role="user", content=user_message, message_type="text")
    db.add(inbound)
    remember_user_message(db, character.id, user_message)
    db.flush()

    recent_messages = list(
        db.scalars(
            select(Message)
            .where(Message.character_id == character.id)
            .order_by(Message.created_at.desc())
            .limit(8)
        )
    )
    reply = generate_reply(character, user_message, list(reversed(recent_messages)))
    build_orchestrator_context(db, character, user_message)
    outbound = Message(character_id=character.id, role="assistant", content=reply, message_type="text")
    db.add(outbound)

    update_state_after_message(character)
    db.commit()
    db.refresh(outbound)
    return reply, outbound
