from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.character import Character, CharacterProfile, CharacterState
from app.models.user import User
from app.schemas.character import CharacterCreate, CharacterRead
from app.services.time_context import infer_timezone

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
    user = character.user
    return CharacterRead(
        id=character.id,
        name=character.name,
        gender=character.gender,
        relationship_mode=character.relationship_mode,
        personality_description=profile.personality_description if profile else "",
        communication_style=profile.communication_style if profile else "",
        background_story=profile.background_story if profile else "",
        biography=(profile.biography or profile.background_story) if profile else "",
        boundaries=profile.boundaries if profile else "",
        likes=profile.likes if profile else "",
        dislikes=profile.dislikes if profile else "",
        language=profile.language if profile else "ru",
        user_nickname=profile.user_nickname if profile else "",
        user_city=user.city if user else "",
        user_country=user.country if user else "",
        user_timezone=user.timezone if user else "Europe/Moscow",
        user_language=user.language if user else "ru",
        created_at=character.created_at,
    )


@router.post("", response_model=CharacterRead)
def create_character(payload: CharacterCreate, db: Session = Depends(get_db)) -> CharacterRead:
    user = get_or_create_demo_user(db)
    user.city = payload.user_city.strip()
    user.country = payload.user_country.strip()
    user.timezone = infer_timezone(user.city, user.country, payload.user_timezone.strip() or "Europe/Moscow")
    user.language = payload.user_language.strip() or payload.language
    if payload.user_nickname.strip():
        user.display_name = payload.user_nickname.strip()
    character = Character(
        user_id=user.id,
        name=payload.name,
        gender=payload.gender,
        relationship_mode=payload.relationship_mode,
    )
    character.profile = CharacterProfile(
        personality_description=payload.personality_description,
        communication_style=payload.communication_style,
        background_story=payload.background_story or payload.biography,
        biography=payload.biography or payload.background_story,
        boundaries=payload.boundaries,
        likes=payload.likes,
        dislikes=payload.dislikes,
        language=payload.language,
        user_nickname=payload.user_nickname,
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
