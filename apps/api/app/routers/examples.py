"""Curated examples are read-only until copied into a user's account."""

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.database import get_db
from app.routers.characters import to_character_read
from app.schemas.character import CharacterRead
from app.security import current_user
from app.services.example_characters import copy_example, list_ready_examples


router = APIRouter(prefix="/examples", tags=["examples"])


@router.get("")
def list_examples(request: Request, db: Session = Depends(get_db)) -> list[dict]:
    current_user(request, db)
    return list_ready_examples()


@router.post("/{slug}/copy", response_model=CharacterRead)
def create_from_example(slug: str, request: Request, db: Session = Depends(get_db)) -> CharacterRead:
    user = current_user(request, db)
    return to_character_read(copy_example(db, user, slug))
