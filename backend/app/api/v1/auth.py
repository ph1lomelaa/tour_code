"""Вход и принятие приглашения."""
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.database import get_db
from app.core.security import create_access_token, hash_invite_token, hash_password, verify_password
from db.models import User

router = APIRouter(prefix="/auth", tags=["auth"])

MIN_PASSWORD_LEN = 8


def user_out(user: User) -> dict:
    if not user.is_active:
        state = "disabled"
    elif not user.password_hash:
        state = "invited"
    else:
        state = "active"
    return {
        "id": str(user.id),
        "email": user.email,
        "full_name": user.full_name or "",
        "role": user.role,
        "status": state,
        "last_login_at": user.last_login_at.isoformat() if user.last_login_at else None,
        "created_at": user.created_at.isoformat() if user.created_at else None,
    }


class LoginIn(BaseModel):
    email: str
    password: str


class AcceptInviteIn(BaseModel):
    full_name: str = Field(min_length=1, max_length=255)
    password: str


def _session(user: User) -> dict:
    return {"access_token": create_access_token(str(user.id)), "token_type": "bearer", "user": user_out(user)}


@router.post("/login")
def login(body: LoginIn, db: Session = Depends(get_db)):
    email = body.email.strip().lower()
    user = db.query(User).filter(func.lower(User.email) == email).first()
    if user is None or not user.is_active or not verify_password(body.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Неверная почта или пароль")
    user.last_login_at = datetime.utcnow()
    db.commit()
    return _session(user)


@router.get("/me")
def me(user: User = Depends(get_current_user)):
    return user_out(user)


def _user_by_invite(db: Session, token: str) -> User:
    user = db.query(User).filter(User.invite_token_hash == hash_invite_token(token)).first()
    if user is None or not user.is_active:
        raise HTTPException(status_code=404, detail="Ссылка недействительна")
    if user.invite_expires_at and user.invite_expires_at < datetime.utcnow():
        raise HTTPException(status_code=410, detail="Срок действия ссылки истёк — попросите новую у администратора")
    return user


@router.get("/invite/{token}")
def invite_info(token: str, db: Session = Depends(get_db)):
    user = _user_by_invite(db, token)
    return {"email": user.email, "full_name": user.full_name or ""}


@router.post("/invite/{token}")
def accept_invite(token: str, body: AcceptInviteIn, db: Session = Depends(get_db)):
    user = _user_by_invite(db, token)
    if len(body.password) < MIN_PASSWORD_LEN:
        raise HTTPException(status_code=422, detail=f"Пароль должен быть не короче {MIN_PASSWORD_LEN} символов")
    user.full_name = body.full_name.strip()
    user.password_hash = hash_password(body.password)
    user.invite_token_hash = None
    user.invite_token = None
    user.invite_expires_at = None
    user.last_login_at = datetime.utcnow()
    db.commit()
    return _session(user)
