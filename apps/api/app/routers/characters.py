from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.character import Character, CharacterProfile, CharacterState
from app.models.user import User
from app.schemas.character import CharacterCreate, CharacterRead

router = APIRouter(prefix="/characters", tags=["characters"])

DEMO_USER_EMAIL = "demo@local"


def get_or_create_demo_user(db: Session) -> User:
    user = db.scalar(select(User).where(User.email == DEMO_USER_EMAIL))
    if user:
        return user
    user = User(email=DEMO_USER_EMAIL, display_name="Demo User")
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def to_character_read(character: Character) -> CharacterRead:
    profile = character.profile
    return CharacterRead(
        id=character.id,
        name=character.name,
        gender=character.gender,
        relationship_mode=character.relationship_mode,
        personality_description=profile.personality_description if profile else "",
        communication_style=profile.communication_style if profile else "",
        background_story=profile.background_story if profile else "",
        boundaries=profile.boundaries if profile else "",
        created_at=character.created_at,
    )


@router.post("", response_model=CharacterRead)
def create_character(payload: CharacterCreate, db: Session = Depends(get_db)) -> CharacterRead:
    user = get_or_create_demo_user(db)
    character = Character(
        user_id=user.id,
        name=payload.name,
        gender=payload.gender,
        relationship_mode=payload.relationship_mode,
    )
    character.profile = CharacterProfile(
        personality_description=payload.personality_description,
        communication_style=payload.communication_style,
        background_story=payload.background_story,
        boundaries=payload.boundaries,
    )
    character.state = CharacterState()
    db.add(character)
    db.commit()
    db.refresh(character)
    return to_character_read(character)


@router.get("", response_model=list[CharacterRead])
def list_characters(db: Session = Depends(get_db)) -> list[CharacterRead]:
    characters = db.scalars(select(Character).order_by(Character.created_at.desc())).all()
    return [to_character_read(character) for character in characters]


@router.get("/{character_id}", response_model=CharacterRead)
def get_character(character_id: str, db: Session = Depends(get_db)) -> CharacterRead:
    character = db.get(Character, character_id)
    if not character:
        raise HTTPException(status_code=404, detail="Character not found")
    return to_character_read(character)
