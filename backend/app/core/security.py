"""Пароли, JWT и токены приглашений."""
import hashlib
import secrets
from datetime import datetime, timedelta
from typing import Optional

import bcrypt
from jose import JWTError, jwt

from app.core.config import settings


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: Optional[str]) -> bool:
    if not password_hash:
        return False
    try:
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))
    except ValueError:
        return False


def create_access_token(user_id: str) -> str:
    """Сессия бессрочная (ACCESS_TOKEN_EXPIRE_MINUTES=0): человек остаётся в системе.
    Доступ всё равно проверяется на каждом запросе — отключение админом действует сразу."""
    claims: dict = {"sub": user_id}
    if settings.ACCESS_TOKEN_EXPIRE_MINUTES > 0:
        claims["exp"] = datetime.utcnow() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    return jwt.encode(claims, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def decode_access_token(token: str) -> Optional[str]:
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
    except JWTError:
        return None
    sub = payload.get("sub")
    return str(sub) if sub else None


def hash_invite_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def new_invite_token() -> tuple[str, str, Optional[datetime]]:
    """Возвращает (токен для ссылки, его хеш для БД, срок действия).
    INVITE_EXPIRE_DAYS=0 — ссылка действует, пока человек не зарегистрируется."""
    token = secrets.token_urlsafe(32)
    expires = None
    if settings.INVITE_EXPIRE_DAYS > 0:
        expires = datetime.utcnow() + timedelta(days=settings.INVITE_EXPIRE_DAYS)
    return token, hash_invite_token(token), expires
