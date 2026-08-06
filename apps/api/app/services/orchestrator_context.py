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
    OrchestratorSceneContext,
    OrchestratorStateContext,
    OrchestratorUserContext,
    OrchestratorWorldStateContext,
)
from app.services.scene_service import get_or_create_scene
from app.services.time_context import (
    DEFAULT_TIMEZONE,
    describe_daylight_context,
    describe_time_of_day,
    get_local_datetime,
    infer_timezone,
)
from app.services.world_state import build_world_state


RECENT_MESSAGE_LIMIT = 12
MEMORY_PER_CATEGORY_LIMIT = 8
WEEKDAYS = ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday")


def build_orchestrator_context(
    db: Session,
    character: Character,
    current_user_message: str,
    recent_message_limit: int = RECENT_MESSAGE_LIMIT,
) -> OrchestratorContext:
    profile = character.profile
    state = character.state
    user = character.user
    user_city = user.city if user else ""
    user_country = user.country if user else ""
    user_timezone = infer_timezone(user_city, user_country, user.timezone if user and user.timezone else DEFAULT_TIMEZONE)
    local_datetime = get_local_datetime(user_timezone)
    scene = get_or_create_scene(db, character)

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

    scene_context = OrchestratorSceneContext(
        presence_mode=scene.presence_mode,
        location_name=scene.location_name,
        location_description=scene.location_description,
        user_position=scene.user_position,
        character_position=scene.character_position,
        can_use_physical_touch=scene.presence_mode in {"same_place", "virtual_roleplay"},
        can_share_immediate_physical_space=scene.presence_mode in {"same_place", "virtual_roleplay"},
    )
    world_state = build_world_state(scene_context)

    return OrchestratorContext(
        character_id=character.id,
        character_name=character.name,
        character_gender=character.gender,
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
        user_context=OrchestratorUserContext(
            display_name=user.display_name if user else "",
            city=user_city,
            country=user_country,
            timezone=user_timezone,
            language=user.language if user else profile.language if profile else "ru",
            local_datetime=local_datetime,
            local_datetime_iso=local_datetime.isoformat(timespec="minutes"),
            local_date=local_datetime.date().isoformat(),
            local_time=local_datetime.strftime("%H:%M"),
            weekday=WEEKDAYS[local_datetime.weekday()],
            time_of_day=describe_time_of_day(local_datetime.hour),
            daylight_context=describe_daylight_context(local_datetime.hour),
        ),
        scene_context=scene_context,
        world_state=OrchestratorWorldStateContext(**world_state),
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
