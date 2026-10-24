from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.database import get_db
from app.security import current_user
from app.services.account_limits import usage_snapshot

router = APIRouter(prefix="/limits", tags=["limits"])


@router.get("")
def limits(request: Request, db: Session = Depends(get_db)) -> dict[str, dict[str, int]]:
    return usage_snapshot(db, current_user(request, db).id)
