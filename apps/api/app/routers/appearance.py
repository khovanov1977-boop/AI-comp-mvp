from fastapi import APIRouter, BackgroundTasks, Depends
from sqlalchemy.orm import Session

from app.database import SessionLocal, get_db
from app.schemas.appearance import AppearanceGenerate, AppearancePublish, AppearanceSelection, AppearanceStage
from app.services.appearance_service import publish_appearance, read_appearance, select_candidate
from app.services.image_generation import run_generation, submit_generation

router = APIRouter(prefix="/characters/{character_id}/appearance", tags=["appearance"])


def get_image_session_factory():
    return SessionLocal


@router.get("")
def get_appearance(character_id: str, db: Session = Depends(get_db)) -> dict:
    return read_appearance(db, character_id)


@router.post("/select/{stage}")
def choose_candidate(character_id: str, stage: AppearanceStage, payload: AppearanceSelection, db: Session = Depends(get_db)) -> dict:
    return select_candidate(db, character_id, stage, payload.candidate_id, payload.expected_revision)


@router.post("/publish")
def confirm_appearance(character_id: str, payload: AppearancePublish, db: Session = Depends(get_db)) -> dict:
    return publish_appearance(db, character_id, payload.expected_revision, payload.confirm_gender_change)


@router.post("/generate/{stage}", status_code=202)
def generate_candidates(
    character_id: str, stage: AppearanceStage, payload: AppearanceGenerate,
    background_tasks: BackgroundTasks, db: Session = Depends(get_db),
    session_factory=Depends(get_image_session_factory),
) -> dict:
    job, created = submit_generation(db, character_id, stage, payload)
    if created:
        background_tasks.add_task(run_generation, job.id, session_factory)
    return read_appearance(db, character_id)
