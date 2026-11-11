"""Управление пользователями (только админ)."""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.api.deps import require_admin
from app.api.v1.auth import user_out
from app.core.database import get_db
from app.core.security import new_invite_token
from db.models import User, UserRole

router = APIRouter(prefix="/users", tags=["users"])

ROLES = {r.value for r in UserRole}


class UserCreate(BaseModel):
    email: EmailStr
    role: str = UserRole.VIEWER.value


class UserUpdate(BaseModel):
    role: Optional[str] = None
    is_active: Optional[bool] = None


def _check_role(role: str) -> str:
    if role not in ROLES:
        raise HTTPException(status_code=422, detail="Неизвестная роль")
    return role


def _get(db: Session, user_id: str) -> User:
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="Пользователь не найден")
    return user


def _issue_invite(user: User) -> str:
    token, token_hash, expires = new_invite_token()
    user.invite_token_hash = token_hash
    user.invite_token = token
    user.invite_expires_at = expires
    return token


def admin_user_out(user: User) -> dict:
    """Для админа — ещё и действующая ссылка-приглашение (чтобы скопировать снова)."""
    data = user_out(user)
    data["invite_token"] = user.invite_token if user.is_active else None
    return data


def _other_active_admins(db: Session, user: User) -> int:
    return (
        db.query(User)
        .filter(User.role == UserRole.ADMIN.value, User.is_active.is_(True), User.id != user.id)
        .count()
    )


@router.get("")
def list_users(db: Session = Depends(get_db), _admin: User = Depends(require_admin)):
    users = db.query(User).order_by(User.created_at.asc()).all()
    return {"items": [admin_user_out(u) for u in users]}


@router.post("")
def create_user(body: UserCreate, db: Session = Depends(get_db), _admin: User = Depends(require_admin)):
    email = str(body.email).strip().lower()
    if db.query(User).filter(func.lower(User.email) == email).first():
        raise HTTPException(status_code=409, detail="Пользователь с такой почтой уже есть")
    user = User(email=email, role=_check_role(body.role), is_active=True)
    token = _issue_invite(user)
    db.add(user)
    db.commit()
    db.refresh(user)
    return {"user": admin_user_out(user), "invite_token": token}


@router.patch("/{user_id}")
def update_user(
    user_id: str, body: UserUpdate,
    db: Session = Depends(get_db), admin: User = Depends(require_admin),
):
    user = _get(db, user_id)
    if str(user.id) == str(admin.id) and (
        (body.role is not None and body.role != UserRole.ADMIN.value) or body.is_active is False
    ):
        raise HTTPException(status_code=400, detail="Нельзя понизить или отключить самого себя")
    if body.role is not None:
        user.role = _check_role(body.role)
    if body.is_active is not None:
        user.is_active = body.is_active
    db.commit()
    return admin_user_out(user)


@router.post("/{user_id}/invite")
def regenerate_invite(user_id: str, db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    """Новая ссылка. Старая перестаёт работать; по ней же можно задать новый пароль."""
    user = _get(db, user_id)
    if str(user.id) == str(admin.id):
        raise HTTPException(status_code=400, detail="Для своего аккаунта ссылку создавать не нужно")
    token = _issue_invite(user)
    user.is_active = True
    db.commit()
    return {"user": admin_user_out(user), "invite_token": token}


@router.delete("/{user_id}")
def delete_user(user_id: str, db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    user = _get(db, user_id)
    if str(user.id) == str(admin.id):
        raise HTTPException(status_code=400, detail="Нельзя удалить самого себя")
    if user.role == UserRole.ADMIN.value and _other_active_admins(db, user) == 0:
        raise HTTPException(status_code=400, detail="Нельзя удалить последнего администратора")
    if user.tours:
        # У пользователя есть туры — отключаем, чтобы не ломать историю.
        user.is_active = False
        user.invite_token_hash = None
        user.invite_token = None
        db.commit()
        return {"ok": True, "disabled": True}
    db.delete(user)
    db.commit()
    return {"ok": True, "disabled": False}
