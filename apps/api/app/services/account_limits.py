from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.account_usage import AccountUsage
from app.models.user import User

ACCOUNT_LIMITS = {
    "images_count": 10,
    "videos_count": 3,
    "text_messages_count": 500,
    "voice_messages_count": 50,
}


def usage_snapshot(db: Session, user_id: str) -> dict[str, dict[str, int]]:
    usage = db.get(AccountUsage, user_id)
    return {key: {"used": getattr(usage, key) if usage else 0, "limit": limit}
            for key, limit in ACCOUNT_LIMITS.items()}


def reserve_account_units(db: Session, user_id: str, kind: str, units: int = 1) -> None:
    if kind not in ACCOUNT_LIMITS or units < 1:
        raise ValueError("Invalid account usage kind or amount")
    # Lock the parent row first, including when the counter row has not been created.
    db.scalar(select(User.id).where(User.id == user_id).with_for_update())
    usage = db.get(AccountUsage, user_id)
    if usage is None:
        usage = AccountUsage(user_id=user_id)
        db.add(usage)
        db.flush()
    remaining = max(0, ACCOUNT_LIMITS[kind] - getattr(usage, kind))
    if units > remaining:
        if kind == "images_count" and remaining:
            raise HTTPException(429, f"Доступно изображений: {remaining}. Для запроса нужно: {units}. Уменьшите количество вариантов.")
        raise HTTPException(429, "Лимит аккаунта исчерпан. Доступные остатки показаны в профиле.")
    setattr(usage, kind, getattr(usage, kind) + units)
    db.flush()


def release_image_units(db: Session, user_id: str, units: int) -> None:
    """Return reserved slots for image outputs that were never delivered."""
    if units < 1:
        return
    db.scalar(select(User.id).where(User.id == user_id).with_for_update())
    usage = db.get(AccountUsage, user_id)
    if usage is None or usage.images_count < units:
        raise ValueError("Image allowance accounting is inconsistent")
    usage.images_count -= units
    db.flush()
