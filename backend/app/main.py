"""
FastAPI Main Application
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import logging

from app.core.config import settings
from app.core.database import check_db_connection, init_db
from app.api.v1 import tours, manifest

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Создаём FastAPI приложение
app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="API для системы управления тур-кодами Hickmet Premium"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=settings.CORS_ALLOW_CREDENTIALS,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============= События приложения =============

@app.on_event("startup")
async def startup_event():
    """При запуске приложения"""
    logger.info(f"🚀 Запуск {settings.APP_NAME} v{settings.APP_VERSION}")
    logger.info(f"Environment: {settings.APP_ENV}")

    # Проверяем подключение к БД
    if check_db_connection():
        logger.info("✅ PostgreSQL подключен")
    else:
        logger.warning("⚠️  PostgreSQL недоступен")

    # Инициализируем БД (создаём таблицы если нужно)
    try:
        init_db()
    except Exception as e:
        logger.error(f"Ошибка инициализации БД: {e}")

    logger.info("✅ Приложение запущено")


@app.on_event("shutdown")
async def shutdown_event():
    """При остановке приложения"""
    logger.info("🛑 Остановка приложения")


# ============= Роутеры =============

# API v1
app.include_router(tours.router, prefix="/api/v1")
app.include_router(manifest.router, prefix="/api/v1")


# ============= Базовые endpoints =============

@app.get("/")
async def root():
    """Корневой endpoint"""
    return {
        "app": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "status": "running",
        "docs": "/docs",
        "redoc": "/redoc"
    }


@app.get("/health")
async def health_check():
    """Health check для мониторинга"""
    db_ok = check_db_connection()

    return {
        "status": "healthy" if db_ok else "degraded",
        "database": "connected" if db_ok else "disconnected",
        "version": settings.APP_VERSION
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG,
        log_level="info"
    )
