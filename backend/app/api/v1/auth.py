"""Вход, заявка на доступ и принятие приглашения."""
import hmac
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.config import settings
from app.core.database import get_db
from app.core.security import create_access_token, hash_invite_token, hash_password, verify_password
from db.models import User, UserRole

router = APIRouter(prefix="/auth", tags=["auth"])

MIN_PASSWORD_LEN = 8


def user_out(user: User) -> dict:
    if not user.is_active:
        state = "disabled"
    elif not user.is_approved:
        state = "pending"
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
    email: str  # почта или логин Камкора (для админа)
    password: str


class RequestAccessIn(BaseModel):
    full_name: str = Field(min_length=1, max_length=255)
    email: str = Field(min_length=3, max_length=255)
    password: str


class AcceptInviteIn(BaseModel):
    full_name: str = Field(min_length=1, max_length=255)
    password: str


def _session(user: User) -> dict:
    return {"access_token": create_access_token(str(user.id)), "token_type": "bearer", "user": user_out(user)}


def _kamkor_admin(db: Session, login: str, password: str) -> User | None:
    """Админ входит логином и паролем Камкора (DISPATCH_AGENT_LOGIN / DISPATCH_AGENT_PASS)."""
    kamkor_login = (settings.DISPATCH_AGENT_LOGIN or "").strip().lower()
    kamkor_pass = settings.DISPATCH_AGENT_PASS or ""
    if "@" in login or not kamkor_login or not kamkor_pass or login != kamkor_login:
        return None
    if not hmac.compare_digest(password.encode("utf-8"), kamkor_pass.encode("utf-8")):
        return None
    admins = db.query(User).filter(User.role == UserRole.ADMIN.value, User.is_active.is_(True))
    admin_email = (settings.ADMIN_EMAIL or "").strip().lower()
    if admin_email:
        user = admins.filter(func.lower(User.email) == admin_email).first()
        if user is not None:
            return user
    return admins.order_by(User.created_at.asc()).first()


@router.post("/login")
def login(body: LoginIn, db: Session = Depends(get_db)):
    identifier = body.email.strip().lower()
    user = _kamkor_admin(db, identifier, body.password)
    if user is None:
        user = db.query(User).filter(func.lower(User.email) == identifier).first()
        if user is None or not user.is_active or not verify_password(body.password, user.password_hash):
            raise HTTPException(status_code=401, detail="Неверная почта или пароль")
        if not user.is_approved:
            raise HTTPException(status_code=403, detail="Заявка ещё не одобрена администратором")
    user.last_login_at = datetime.utcnow()
    db.commit()
    return _session(user)


@router.post("/request-access")
def request_access(body: RequestAccessIn, db: Session = Depends(get_db)):
    """Заявка на доступ: человек сам задаёт имя, почту и пароль, админ потом принимает."""
    email = body.email.strip().lower()
    if "@" not in email:
        raise HTTPException(status_code=422, detail="Укажите почту")
    if len(body.password) < MIN_PASSWORD_LEN:
        raise HTTPException(status_code=422, detail=f"Пароль должен быть не короче {MIN_PASSWORD_LEN} символов")
    if db.query(User).filter(func.lower(User.email) == email).first():
        raise HTTPException(status_code=409, detail="Пользователь с такой почтой уже есть или заявка уже отправлена")
    user = User(
        email=email,
        full_name=body.full_name.strip(),
        password_hash=hash_password(body.password),
        role=UserRole.VIEWER.value,
        is_active=True,
        is_approved=False,
    )
    db.add(user)
    db.commit()
    return {"ok": True}


@router.get("/me")
def me(user: User = Depends(get_current_user)):
    return user_out(user)


def _user_by_invite(db: Session, token: str) -> User:
    user = db.query(User).filter(User.invite_token_hash == hash_invite_token(token)).first()
    if user is None or not user.is_active or not user.is_approved:
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
