from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.character import Character
from app.models.user import User
from app.schemas.user import UserProfileUpdate, UserRead
from app.services.time_context import infer_timezone


router = APIRouter(prefix="/users", tags=["users"])
NAME_FIELDS = ("display_name", "formal_name", "preferred_name", "casual_name", "vocative_name")


@router.patch("/profile", response_model=UserRead)
def update_user_profile(payload: UserProfileUpdate, db: Session = Depends(get_db)) -> UserRead:
    character = db.get(Character, payload.character_id)
    if not character or not character.user:
        raise HTTPException(status_code=404, detail="User profile not found")

    user: User = character.user
    changed_fields = payload.model_fields_set

    for field_name in NAME_FIELDS:
        if field_name in changed_fields:
            setattr(user, field_name, (getattr(payload, field_name) or "").strip())

    if "age" in changed_fields:
        user.age = payload.age
    if "city" in changed_fields:
        user.city = (payload.city or "").strip()
    if "country" in changed_fields:
        user.country = (payload.country or "").strip()
    if "language" in changed_fields:
        user.language = (payload.language or "").strip() or "ru"
    if {"city", "country", "timezone"} & changed_fields:
        requested_timezone = (payload.timezone or user.timezone or "Europe/Moscow").strip()
        user.timezone = infer_timezone(user.city, user.country, requested_timezone)

    db.add(user)
    db.commit()
    db.refresh(user)
    return user
