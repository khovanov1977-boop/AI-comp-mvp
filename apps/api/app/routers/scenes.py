from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.character import Character
from app.schemas.scene import SceneRead, SceneUpdate
from app.services.scene_service import get_or_create_scene, update_scene

router = APIRouter(prefix="/scenes", tags=["scenes"])


@router.get("/{character_id}", response_model=SceneRead)
def get_scene(character_id: str, db: Session = Depends(get_db)) -> SceneRead:
    character = db.get(Character, character_id)
    if not character:
        raise HTTPException(status_code=404, detail="Character not found")
    return get_or_create_scene(db, character)


@router.put("", response_model=SceneRead)
def put_scene(payload: SceneUpdate, db: Session = Depends(get_db)) -> SceneRead:
    character = db.get(Character, payload.character_id)
    if not character:
        raise HTTPException(status_code=404, detail="Character not found")
    try:
        return update_scene(db, character, payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
