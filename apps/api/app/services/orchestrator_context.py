from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.character import Character
from app.models.memory import Memory
from app.models.message import Message
from app.schemas.orchestrator import (
    MEMORY_CATEGORIES,
    OrchestratorContext,
    OrchestratorMemoryItem,
    OrchestratorMessageContext,
    OrchestratorProfileContext,
    OrchestratorStateContext,
)


RECENT_MESSAGE_LIMIT = 12
MEMORY_PER_CATEGORY_LIMIT = 8


def build_orchestrator_context(
    db: Session,
    character: Character,
    current_user_message: str,
    recent_message_limit: int = RECENT_MESSAGE_LIMIT,
) -> OrchestratorContext:
    profile = character.profile
    state = character.state

    recent_messages = list(
        db.scalars(
            select(Message)
            .where(Message.character_id == character.id)
            .order_by(Message.created_at.desc())
            .limit(recent_message_limit)
        )
    )
    recent_messages.reverse()

    memories_by_category: dict[str, list[OrchestratorMemoryItem]] = {}
    for category in MEMORY_CATEGORIES:
        memories = list(
            db.scalars(
                select(Memory)
                .where(Memory.character_id == character.id, Memory.memory_type == category)
                .order_by(Memory.importance.desc(), Memory.created_at.desc())
                .limit(MEMORY_PER_CATEGORY_LIMIT)
            )
        )
        memories_by_category[category] = [
            OrchestratorMemoryItem(
                id=memory.id,
                content=memory.content,
                importance=memory.importance,
                created_at=memory.created_at,
            )
            for memory in memories
        ]

    return OrchestratorContext(
        character_id=character.id,
        character_name=character.name,
        relationship_mode=character.relationship_mode,
        profile=OrchestratorProfileContext(
            personality_description=profile.personality_description if profile else "",
            communication_style=profile.communication_style if profile else "",
            biography=(profile.biography or profile.background_story) if profile else "",
            boundaries=profile.boundaries if profile else "",
            likes=profile.likes if profile else "",
            dislikes=profile.dislikes if profile else "",
            language=profile.language if profile else "ru",
            user_nickname=profile.user_nickname if profile else "",
        ),
        state=OrchestratorStateContext(
            mood=state.mood,
            trust=state.trust_level,
            attachment=state.attachment_level,
            energy=state.energy_level,
        ),
        memory=memories_by_category,
        recent_messages=[
            OrchestratorMessageContext(
                role=message.role,
                content=message.content,
                message_type=message.message_type,
                created_at=message.created_at,
            )
            for message in recent_messages
        ],
        current_user_message=current_user_message,
    )
