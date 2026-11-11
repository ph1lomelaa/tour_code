"""Создание первого администратора из env при старте."""
import logging

from app.core.config import settings
from app.core.database import SessionLocal
from app.core.security import hash_password
from db.models import User, UserRole

logger = logging.getLogger(__name__)


def ensure_admin() -> None:
    if not settings.CREATE_ADMIN_ON_STARTUP:
        return
    email = settings.ADMIN_EMAIL.strip().lower()
    if not email or not settings.ADMIN_PASSWORD:
        logger.warning("CREATE_ADMIN_ON_STARTUP включён, но ADMIN_EMAIL/ADMIN_PASSWORD не заданы")
        return
    with SessionLocal() as db:
        if db.query(User).filter(User.role == UserRole.ADMIN.value).first():
            return
        user = db.query(User).filter(User.email == email).first()
        if user is None:
            user = User(email=email)
            db.add(user)
        user.role = UserRole.ADMIN.value
        user.full_name = user.full_name or settings.ADMIN_FULL_NAME
        user.password_hash = hash_password(settings.ADMIN_PASSWORD)
        user.is_active = True
        db.commit()
        logger.info("Создан администратор %s", email)
