from sqlalchemy.orm import Session
from sqlalchemy import select

from app.models.character import Character
from app.models.message import Message
from app.providers.llm_factory import get_llm_provider
from app.schemas.llm import CharacterReply
from app.services.character_engine import update_state_after_message
from app.services.orchestrator_context import build_orchestrator_context
from app.services.memory_service import remember_user_message
from app.services.reply_renderer import normalize_character_reply, render_character_reply
from app.services.voice_intent import should_generate_voice_reply


def generate_assistant_reply(
    db: Session,
    character: Character,
    user_message: str,
    voice_reply_requested: bool | None = None,
) -> tuple[str, Message, CharacterReply]:
    context = build_orchestrator_context(
        db,
        character,
        user_message,
        recent_message_limit=8,
        voice_reply_requested=voice_reply_requested,
    )
    reply_plan = normalize_character_reply(get_llm_provider().generate_reply(context))
    reply = render_character_reply(reply_plan)
    outbound = Message(character_id=character.id, role="assistant", content=reply, message_type="text")
    db.add(outbound)

    update_state_after_message(character, user_message)
    db.commit()
    db.refresh(outbound)
    return reply, outbound, reply_plan


def handle_chat_message(
    db: Session,
    character: Character,
    user_message: str,
) -> tuple[str, Message, CharacterReply]:
    inbound = Message(character_id=character.id, role="user", content=user_message, message_type="text")
    db.add(inbound)
    db.commit()

    return handle_existing_user_message(db, character, inbound)


def handle_existing_user_message(
    db: Session,
    character: Character,
    inbound: Message,
) -> tuple[str, Message, CharacterReply]:
    if inbound.character_id != character.id or inbound.role != "user" or not inbound.content.strip():
        raise ValueError("A non-empty user message is required")

    user_message = inbound.content
    remember_user_message(db, character.id, user_message)
    db.commit()
    db.refresh(character)

    return generate_assistant_reply(
        db,
        character,
        user_message,
        voice_reply_requested=(
            inbound.message_type == "voice" or should_generate_voice_reply(user_message)
        ),
    )


def retry_last_user_message(
    db: Session,
    character: Character,
) -> tuple[str, Message, CharacterReply]:
    last_message = db.scalar(
        select(Message)
        .where(Message.character_id == character.id)
        .order_by(Message.created_at.desc())
        .limit(1)
    )
    if not last_message or last_message.role != "user":
        raise ValueError("No failed user message to retry")

    return generate_assistant_reply(
        db,
        character,
        last_message.content,
        voice_reply_requested=(
            last_message.message_type == "voice"
            or should_generate_voice_reply(last_message.content)
        ),
    )
