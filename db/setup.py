import os
import logging

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import sessionmaker

from .models import Base

logger = logging.getLogger(__name__)

_BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_DEFAULT_DB = f"sqlite:///{os.path.join(_BASE_DIR, 'hickmet.db')}"

DATABASE_URL = os.getenv("DATABASE_URL", _DEFAULT_DB)

_is_sqlite = DATABASE_URL.startswith("sqlite")

engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
    **({} if _is_sqlite else {"pool_recycle": 1800, "pool_size": 20, "max_overflow": 40}),
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """Создаёт все таблицы если их нет. Вызывать при старте приложения."""
    Base.metadata.create_all(bind=engine)
    _apply_lightweight_migrations()
    logger.info("База данных инициализирована: %s", DATABASE_URL)


def _apply_lightweight_migrations() -> None:
    inspector = inspect(engine)
    if "pilgrims" not in inspector.get_table_names():
        return

    columns = {column["name"] for column in inspector.get_columns("pilgrims")}
    with engine.begin() as conn:
        if "tour_code" not in columns:
            conn.execute(text("ALTER TABLE pilgrims ADD COLUMN tour_code VARCHAR(64)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_pilgrims_tour_code ON pilgrims (tour_code)"))


def check_connection() -> bool:
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        logger.info("Подключение к БД успешно")
        return True
    except Exception as e:
        logger.error("Ошибка подключения к БД: %s", e)
        return False
