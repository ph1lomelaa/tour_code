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
    from .seed_reference import seed_reference_data

    with SessionLocal() as db:
        seed_reference_data(db)
    logger.info("База данных инициализирована: %s", DATABASE_URL)


def _apply_lightweight_migrations() -> None:
    inspector = inspect(engine)
    tables = inspector.get_table_names()
    if "users" in tables:
        _migrate_users(inspector)
    if "admin_audit_log" in tables:
        audit_columns = {c["name"] for c in inspector.get_columns("admin_audit_log")}
        if "user_email" not in audit_columns:
            with engine.begin() as conn:
                conn.execute(text("ALTER TABLE admin_audit_log ADD COLUMN user_email VARCHAR(255)"))
    if "pilgrims" not in tables:
        return

    columns = {column["name"] for column in inspector.get_columns("pilgrims")}
    with engine.begin() as conn:
        if "tour_code" not in columns:
            conn.execute(text("ALTER TABLE pilgrims ADD COLUMN tour_code VARCHAR(64)"))
        # Партнёр отдаёт два кода: q_number ("Tour code number") и
        # q_short_number ("Tour code old number"). Храним оба.
        if "tour_code_old" not in columns:
            conn.execute(text("ALTER TABLE pilgrims ADD COLUMN tour_code_old VARCHAR(64)"))
        if "resident_status" not in columns:
            conn.execute(text("ALTER TABLE pilgrims ADD COLUMN resident_status VARCHAR(20) NOT NULL DEFAULT 'резидент'"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_pilgrims_tour_code ON pilgrims (tour_code)"))
        # Старый глобальный уникальный индекс блокировал повторную отправку
        # того же паломника в разных турах. Дедуп теперь в рамках одного тура.
        conn.execute(text("DROP INDEX IF EXISTS ux_pilgrims_document_norm"))
        _deduplicate_pilgrims_by_document(conn)
        conn.execute(
            text(
                """
                CREATE UNIQUE INDEX IF NOT EXISTS ux_pilgrims_tour_document_norm
                ON pilgrims (tour_id, UPPER(TRIM(document)))
                WHERE document IS NOT NULL AND TRIM(document) <> ''
                """
            )
        )


def _migrate_users(inspector) -> None:
    """Приводит старую таблицу users к виду для входа по приглашениям."""
    columns = {c["name"]: c for c in inspector.get_columns("users")}
    with engine.begin() as conn:
        if "invite_token_hash" not in columns:
            conn.execute(text("ALTER TABLE users ADD COLUMN invite_token_hash VARCHAR(64)"))
        if "invite_token" not in columns:
            conn.execute(text("ALTER TABLE users ADD COLUMN invite_token VARCHAR(64)"))
        if "invite_expires_at" not in columns:
            conn.execute(text("ALTER TABLE users ADD COLUMN invite_expires_at TIMESTAMP"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_users_invite_token_hash ON users (invite_token_hash)"))
        if _is_sqlite:
            return
        # Postgres: роль была native enum (user_role / userrole) — переводим в строку.
        role_type = conn.execute(text(
            "SELECT data_type FROM information_schema.columns "
            "WHERE table_name = 'users' AND column_name = 'role' AND table_schema = current_schema()"
        )).scalar()
        if role_type == "USER-DEFINED":
            conn.execute(text("ALTER TABLE users ALTER COLUMN role DROP DEFAULT"))
            conn.execute(text("ALTER TABLE users ALTER COLUMN role TYPE VARCHAR(20) USING LOWER(role::text)"))
        conn.execute(text("ALTER TABLE users ALTER COLUMN role SET DEFAULT 'viewer'"))
        conn.execute(text("UPDATE users SET role = 'editor' WHERE role = 'manager'"))
        conn.execute(text("UPDATE users SET role = 'viewer' WHERE role = 'operator'"))
        conn.execute(text("ALTER TABLE users ALTER COLUMN password_hash DROP NOT NULL"))
        conn.execute(text("ALTER TABLE users ALTER COLUMN full_name DROP NOT NULL"))


def _deduplicate_pilgrims_by_document(conn) -> None:
    """Удаляет дубли паломников в рамках одного тура (по tour_id + document)."""
    rows = conn.execute(
        text(
            """
            SELECT id, tour_id, document, tour_code, created_at
            FROM pilgrims
            WHERE document IS NOT NULL AND TRIM(document) <> ''
            ORDER BY
                tour_id ASC,
                UPPER(TRIM(document)) ASC,
                CASE WHEN COALESCE(tour_code, '') <> '' THEN 0 ELSE 1 END ASC,
                created_at ASC,
                id ASC
            """
        )
    ).mappings().all()

    seen_keys: set[tuple[str, str]] = set()
    duplicate_ids: list[str] = []

    for row in rows:
        normalized_document = str(row["document"] or "").strip().upper()
        if not normalized_document:
            continue
        key = (str(row["tour_id"]), normalized_document)
        if key in seen_keys:
            duplicate_ids.append(str(row["id"]))
            continue
        seen_keys.add(key)

    for duplicate_id in duplicate_ids:
        conn.execute(text("DELETE FROM pilgrims WHERE id = :id"), {"id": duplicate_id})

    if duplicate_ids:
        logger.warning("Removed %s duplicate pilgrims by (tour_id, document) before unique index", len(duplicate_ids))


def check_connection() -> bool:
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        logger.info("Подключение к БД успешно")
        return True
    except Exception as e:
        logger.error("Ошибка подключения к БД: %s", e)
        return False
