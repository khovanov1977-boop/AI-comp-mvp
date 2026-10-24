"""Session authentication and a single ownership boundary for HTTP routes."""

from datetime import datetime, timedelta, timezone
from hashlib import pbkdf2_hmac, sha256
from hmac import compare_digest
import json
import secrets

from fastapi import HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.character import Character
from app.models.memory import Memory
from app.models.message import Message
from app.models.user import User, UserSession
from app.services.image_storage import character_storage_key

SESSION_COOKIE = "ai_comp_session"
SESSION_AGE = timedelta(days=30)
PASSWORD_ITERATIONS = 600_000


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = pbkdf2_hmac("sha256", password.encode(), salt, PASSWORD_ITERATIONS)
    return f"pbkdf2_sha256${PASSWORD_ITERATIONS}${salt.hex()}${digest.hex()}"


def verify_password(password: str, encoded: str | None) -> bool:
    if not encoded:
        return False
    try:
        algorithm, iterations, salt, digest = encoded.split("$", 3)
        if algorithm != "pbkdf2_sha256" or int(iterations) < 100_000:
            return False
        actual = pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), int(iterations))
        return compare_digest(actual, bytes.fromhex(digest))
    except (ValueError, TypeError):
        return False


def create_session(db: Session, user: User) -> str:
    token = secrets.token_urlsafe(32)
    db.add(UserSession(token_hash=sha256(token.encode()).hexdigest(), user_id=user.id,
                       expires_at=datetime.now(timezone.utc).replace(tzinfo=None) + SESSION_AGE))
    db.commit()
    return token


def get_session_user(db: Session, token: str) -> User | None:
    if not token:
        return None
    session = db.get(UserSession, sha256(token.encode()).hexdigest())
    if not session or session.expires_at <= datetime.now(timezone.utc).replace(tzinfo=None):
        return None
    return db.get(User, session.user_id)


def current_user(request: Request, db: Session) -> User:
    user = db.get(User, getattr(request.state, "user_id", None))
    if not user:
        raise HTTPException(401, "Войдите в аккаунт.")
    return user


async def check_owner(request: Request, db: Session, user_id: str) -> None:
    """Fail closed for all character and media routes, including ID-only mutations."""
    segments = [part for part in request.url.path.split("/") if part]
    if not segments:
        return
    root = segments[0]
    character_id = ""
    if root in {"media-files", "voice-files"}:
        if len(segments) != 3:
            raise HTTPException(404, "Файл не найден.")
        owned_ids = db.scalars(select(Character.id).where(Character.user_id == user_id)).all()
        if segments[1] not in {character_storage_key(value) for value in owned_ids}:
            raise HTTPException(404, "Файл не найден.")
        return
    if root == "characters" and len(segments) > 1 and segments[1] != "biography-variants":
        character_id = segments[1]
    elif root == "chat" and len(segments) > 1 and segments[1] != "retry":
        character_id = segments[1]
    elif root in {"scenes", "media"} and len(segments) > 1 and segments[1] not in {"image", "video"}:
        character_id = segments[1]
    elif root == "video" and len(segments) > 1 and segments[1] != "quote":
        character_id = segments[1]
    elif root == "voice" and len(segments) > 2 and segments[1] == "messages":
        identifier = segments[2]
        if len(segments) == 3 or segments[3] == "upload":
            character_id = identifier
        else:
            message = db.get(Message, identifier)
            character_id = message.character_id if message else "missing"
    elif root == "memories" and len(segments) > 1:
        memory = db.get(Memory, segments[1])
        character_id = memory.character_id if memory else "missing"

    if root in {"chat", "scenes", "media", "memories", "users", "debug"} and request.method in {"POST", "PUT", "PATCH"}:
        content_type = request.headers.get("content-type", "")
        if "application/json" in content_type:
            try:
                payload = json.loads(await request.body())
                if isinstance(payload, dict) and payload.get("character_id"):
                    body_id = payload["character_id"]
                    if character_id and character_id != body_id:
                        raise HTTPException(404, "Персонаж не найден.")
                    character_id = body_id
            except json.JSONDecodeError:
                pass
    if character_id and not db.scalar(select(Character.id).where(
        Character.id == character_id, Character.user_id == user_id
    )):
        raise HTTPException(404, "Персонаж не найден.")
