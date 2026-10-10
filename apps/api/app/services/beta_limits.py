"""Small closed-beta hard caps for paid submissions (one API process per instance)."""

from threading import RLock

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.config import settings
from app.models.beta_usage import BetaUsage


PAID_SUBMISSION_LOCK = RLock()


def paid_limit_reason(db: Session, kind: str, units: int = 1) -> str:
    if kind == "image":
        limit = settings.beta_max_image_outputs
    elif kind == "video":
        limit = settings.beta_max_video_requests
    else:
        raise ValueError("Unknown paid request kind")
    if limit < 0:
        return ""
    usage = db.get(BetaUsage, kind)
    if (usage.used if usage else 0) + units > limit:
        return "Лимит платных генераций на этом тестовом стенде исчерпан."
    return ""


def reserve_paid_units(db: Session, kind: str, units: int) -> None:
    if kind == "image":
        limit = settings.beta_max_image_outputs
    elif kind == "video":
        limit = settings.beta_max_video_requests
    else:
        raise ValueError("Unknown paid request kind")
    if limit < 0:
        return
    if units < 1:
        raise ValueError("Paid request units must be positive")
    usage = db.get(BetaUsage, kind, with_for_update=True)
    if usage is None:
        usage = BetaUsage(kind=kind, used=0)
        db.add(usage)
        db.flush()
    if usage.used + units > limit:
        raise HTTPException(429, "Лимит платных генераций на этом тестовом стенде исчерпан.")
    usage.used += units
    db.flush()
