from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.character import Character
from app.schemas.orchestrator import OrchestratorContext, OrchestratorContextDebugRequest
from app.services.orchestrator_context import build_orchestrator_context

router = APIRouter(prefix="/debug", tags=["debug"])


@router.post("/orchestrator-context", response_model=OrchestratorContext)
def inspect_orchestrator_context(
    payload: OrchestratorContextDebugRequest,
    db: Session = Depends(get_db),
) -> OrchestratorContext:
    character = db.get(Character, payload.character_id)
    if not character:
        raise HTTPException(status_code=404, detail="Character not found")

    return build_orchestrator_context(db, character, payload.message)
