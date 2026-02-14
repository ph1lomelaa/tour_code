
import logging

from sqlalchemy import text

from db.base import Base
from db.models import *  # noqa: F401,F403 — чтобы Base увидел все таблицы
from db.setup import engine, SessionLocal, get_db, init_db as setup_init_db  # noqa: F401

logger = logging.getLogger(__name__)


def init_db():
    logger.info("Инициализация базы данных...")
    setup_init_db()
    logger.info("База данных инициализирована")


def check_db_connection():
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        logger.info("Подключение к БД успешно")
        return True
    except Exception as e:
        logger.error("Ошибка подключения к БД: %s", e)
        return False
