"""Curated examples are read-only until copied into a user's account."""

from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy.orm import Session

from app.database import get_db
from app.routers.characters import to_character_read
from app.schemas.character import CharacterRead
from app.security import SESSION_COOKIE, current_user, get_session_user
from app.services.example_characters import copy_example, list_ready_examples


router = APIRouter(prefix="/examples", tags=["examples"])


@router.get("")
def list_examples(request: Request, response: Response, db: Session = Depends(get_db)) -> list[dict]:
    response.headers["Cache-Control"] = "private, no-store"
    examples = list_ready_examples()
    if not get_session_user(db, request.cookies.get(SESSION_COOKIE, "")):
        for item in examples:
            item["images"].pop("body", None)
    return examples


@router.post("/{slug}/copy", response_model=CharacterRead)
def create_from_example(slug: str, request: Request, db: Session = Depends(get_db)) -> CharacterRead:
    user = current_user(request, db)
    return to_character_read(copy_example(db, user, slug))
