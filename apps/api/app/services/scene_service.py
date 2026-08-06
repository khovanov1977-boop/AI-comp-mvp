from sqlalchemy.orm import Session

from app.models.character import Character, CharacterScene
from app.schemas.scene import PRESENCE_MODES, SceneUpdate


DEFAULT_SCENE = {
    "presence_mode": "remote_chat",
    "location_name": "Private chat",
    "location_description": "The user and character are chatting remotely from their own places.",
    "user_position": "at their own place",
    "character_position": "at their own place",
}


def get_or_create_scene(db: Session, character: Character) -> CharacterScene:
    if character.scene:
        return character.scene

    scene = CharacterScene(character_id=character.id, **DEFAULT_SCENE)
    db.add(scene)
    db.commit()
    db.refresh(scene)
    db.refresh(character)
    return scene


def update_scene(db: Session, character: Character, payload: SceneUpdate) -> CharacterScene:
    if payload.presence_mode not in PRESENCE_MODES:
        raise ValueError("Unsupported presence mode")

    scene = get_or_create_scene(db, character)
    scene.presence_mode = payload.presence_mode
    scene.location_name = payload.location_name.strip() or DEFAULT_SCENE["location_name"]
    scene.location_description = payload.location_description.strip()
    scene.user_position = payload.user_position.strip() or DEFAULT_SCENE["user_position"]
    scene.character_position = payload.character_position.strip() or DEFAULT_SCENE["character_position"]
    db.add(scene)
    db.commit()
    db.refresh(scene)
    return scene
