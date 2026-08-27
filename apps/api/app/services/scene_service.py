from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.character import Character, CharacterScene
from app.models.memory import Memory
from app.models.message import Message
from app.schemas.scene import PRESENCE_MODES, SceneUpdate


DEFAULT_SCENE = {
    "presence_mode": "remote_chat",
    "location_name": "Private chat",
    "location_description": "The user and character are chatting remotely from their own places.",
    "time_description": "",
    "user_position": "at their own place",
    "character_position": "at their own place",
}

SCENE_MEMORY_MESSAGE_LIMIT = 6
SCENE_MEMORY_MESSAGE_CHARS = 240


def compact_message(content: str) -> str:
    compact = " ".join(content.split())
    if len(compact) <= SCENE_MEMORY_MESSAGE_CHARS:
        return compact
    return f"{compact[: SCENE_MEMORY_MESSAGE_CHARS - 1].rstrip()}…"


def utc_now_naive() -> datetime:
    """Return UTC in the naive format used by the existing database columns."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


def build_finished_scene_memory(
    db: Session,
    character: Character,
    scene: CharacterScene,
    user_summary: str,
) -> Memory:
    message_query = (
        select(Message)
        .where(Message.character_id == character.id, Message.role == "user")
        .order_by(Message.created_at.desc())
        .limit(SCENE_MEMORY_MESSAGE_LIMIT)
    )
    if scene.context_started_at is not None:
        message_query = message_query.where(Message.created_at >= scene.context_started_at)

    recent_messages = list(db.scalars(message_query))
    recent_messages.reverse()

    memory_parts = [f"Finished shared scene: {scene.location_name}."]
    summary = user_summary.strip()
    if summary:
        memory_parts.append(f"What happened: {summary}")
    else:
        if scene.location_description.strip():
            memory_parts.append(f"Scene context: {scene.location_description.strip()}")
        if scene.time_description.strip():
            memory_parts.append(f"Scene time: {scene.time_description.strip()}")
        if recent_messages:
            exchange = " | ".join(
                f"{message.role}: {compact_message(message.content)}" for message in recent_messages
            )
            memory_parts.append(
                "Past-scene user statements (historical; relative time words belong to that old scene): "
                f"{exchange}"
            )
    memory_parts.append(
        "This is shared past experience, not the current physical scene. Its old place, positions, "
        "relative dates, plans, and unfinished actions must never be treated as current."
    )

    memory = Memory(
        character_id=character.id,
        memory_type="life_event",
        content=" ".join(memory_parts),
        importance=4,
    )
    db.add(memory)
    return memory


def get_or_create_scene(db: Session, character: Character) -> CharacterScene:
    if character.scene:
        return character.scene

    existing_scene = db.scalar(select(CharacterScene).where(CharacterScene.character_id == character.id))
    if existing_scene:
        return existing_scene

    scene = CharacterScene(character_id=character.id, **DEFAULT_SCENE)
    db.add(scene)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        existing_scene = db.scalar(select(CharacterScene).where(CharacterScene.character_id == character.id))
        if existing_scene:
            return existing_scene
        raise
    db.refresh(scene)
    db.refresh(character)
    return scene


def update_scene(db: Session, character: Character, payload: SceneUpdate) -> CharacterScene:
    if payload.presence_mode not in PRESENCE_MODES:
        raise ValueError("Unsupported presence mode")

    scene = get_or_create_scene(db, character)
    if payload.start_new_scene:
        build_finished_scene_memory(db, character, scene, payload.previous_scene_summary)
        scene.context_started_at = utc_now_naive()
        scene.context_timestamp_basis = "utc"
    scene.presence_mode = payload.presence_mode
    scene.location_name = payload.location_name.strip() or DEFAULT_SCENE["location_name"]
    scene.location_description = payload.location_description.strip()
    scene.time_description = payload.time_description.strip()
    scene.user_position = payload.user_position.strip() or DEFAULT_SCENE["user_position"]
    scene.character_position = payload.character_position.strip() or DEFAULT_SCENE["character_position"]
    db.add(scene)
    db.commit()
    db.refresh(scene)
    return scene
