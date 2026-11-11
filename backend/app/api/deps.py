"""Зависимости авторизации: кто вошёл и что ему можно."""
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import decode_access_token
from db.models import User, UserRole

_bearer = HTTPBearer(auto_error=False)

EDIT_ROLES = {UserRole.ADMIN.value, UserRole.EDITOR.value}
READ_METHODS = {"GET", "HEAD", "OPTIONS"}


def get_current_user(
    creds: HTTPAuthorizationCredentials | None = Depends(_bearer),
    db: Session = Depends(get_db),
) -> User:
    unauthorized = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Требуется вход",
        headers={"WWW-Authenticate": "Bearer"},
    )
    if creds is None:
        raise unauthorized
    user_id = decode_access_token(creds.credentials)
    if not user_id:
        raise unauthorized
    user = db.get(User, user_id)
    if user is None or not user.is_active or not user.password_hash:
        raise unauthorized
    return user


def require_access(request: Request, user: User = Depends(get_current_user)) -> User:
    """Просмотр — только чтение; изменения — редактор или админ."""
    if request.method not in READ_METHODS and user.role not in EDIT_ROLES:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Нет прав на изменение")
    return user


def require_admin(user: User = Depends(get_current_user)) -> User:
    if user.role != UserRole.ADMIN.value:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Только для администратора")
    return user
