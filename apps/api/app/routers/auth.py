from hashlib import sha256
import re

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database import get_db
from app.config import settings
from app.models.user import User, UserConsent, UserSession
from app.schemas.user import UserRead
from app.security import SESSION_AGE, SESSION_COOKIE, create_session, current_user, hash_password, verify_password

router = APIRouter(prefix="/auth", tags=["auth"])
CONSENT_VERSION = "2026-10-24"


class RegisterRequest(BaseModel):
    email: str = Field(min_length=5, max_length=254)
    password: str = Field(min_length=10, max_length=128)
    display_name: str = Field(min_length=1, max_length=100)
    privacy_consent: bool


class LoginRequest(BaseModel):
    email: str
    password: str


def normalized_email(value: str) -> str:
    email = value.strip().casefold()
    if not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", email):
        raise HTTPException(422, "Укажите действительный адрес электронной почты.")
    return email


def set_session_cookie(response: Response, request: Request, token: str) -> None:
    response.set_cookie(SESSION_COOKIE, token, max_age=int(SESSION_AGE.total_seconds()),
                        httponly=True, secure=settings.frontend_origin.startswith("https://") or request.url.scheme == "https",
                        samesite="lax", path="/")


@router.post("/register", response_model=UserRead, status_code=201)
def register(payload: RegisterRequest, request: Request, response: Response,
             db: Session = Depends(get_db)) -> UserRead:
    email = normalized_email(payload.email)
    name = payload.display_name.strip()
    if not name:
        raise HTTPException(422, "Введите имя.")
    if not payload.privacy_consent:
        raise HTTPException(422, "Для регистрации необходимо согласие на обработку данных.")
    user = User(email=email, display_name=name, password_hash=hash_password(payload.password))
    try:
        db.add(user)
        db.flush()
        db.add(UserConsent(user_id=user.id, version=CONSENT_VERSION))
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(409, "Этот адрес уже зарегистрирован.") from exc
    db.refresh(user)
    set_session_cookie(response, request, create_session(db, user))
    return user


@router.post("/login", response_model=UserRead)
def login(payload: LoginRequest, request: Request, response: Response,
          db: Session = Depends(get_db)) -> UserRead:
    user = db.scalar(select(User).where(User.email == normalized_email(payload.email)))
    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(401, "Неверная почта или пароль.")
    set_session_cookie(response, request, create_session(db, user))
    return user


@router.get("/me", response_model=UserRead)
def me(request: Request, db: Session = Depends(get_db)) -> UserRead:
    return current_user(request, db)


@router.post("/logout")
def logout(request: Request, response: Response, db: Session = Depends(get_db)) -> dict[str, str]:
    token = request.cookies.get(SESSION_COOKIE, "")
    if token:
        session = db.get(UserSession, sha256(token.encode()).hexdigest())
        if session:
            db.delete(session)
            db.commit()
    response.delete_cookie(SESSION_COOKIE, path="/")
    return {"status": "ok"}
