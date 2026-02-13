"""
Configuration settings
"""
from pydantic_settings import BaseSettings
from typing import List


class Settings(BaseSettings):
    """Настройки приложения"""

    # Application
    APP_NAME: str = "Hickmet Premium API"
    APP_VERSION: str = "1.0.0"
    APP_ENV: str = "development"
    DEBUG: bool = True

    # Server
    HOST: str = "0.0.0.0"
    PORT: int = 8000

    # Database
    DATABASE_URL: str = "postgresql+psycopg2://postgres:postgres@localhost:5432/hickmet"
    DATABASE_POOL_SIZE: int = 20
    DATABASE_MAX_OVERFLOW: int = 40

    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"
    REDIS_MAX_CONNECTIONS: int = 10

    # Security
    SECRET_KEY: str = "your-secret-key-change-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # CORS
    CORS_ORIGINS: List[str] = ["http://localhost:3000", "http://localhost:5173", "http://localhost:5174"]
    CORS_ALLOW_CREDENTIALS: bool = True

    # Google Sheets
    GOOGLE_SHEETS_CREDENTIALS_FILE: str = "./credentials/credentials.json"
    GOOGLE_SHEETS_SPREADSHEET_ID: str = ""

    # File Storage
    UPLOAD_DIR: str = "./uploads"
    MAX_UPLOAD_SIZE_MB: int = 10
    ALLOWED_EXTENSIONS: List[str] = [".xlsx", ".xls", ".csv"]

    # Logging
    LOG_LEVEL: str = "INFO"

    # Dispatch queue / broker
    DISPATCH_TARGET_URL: str = ""
    DISPATCH_REQUEST_TIMEOUT_SECONDS: int = 30
    DISPATCH_MAX_ATTEMPTS: int = 5
    DISPATCH_RETRY_DELAY_SECONDS: int = 60
    DISPATCH_QUEUE_NAME: str = "tour_dispatch"

    # External payload defaults (voucher/partner/queries)
    DISPATCH_MODULE: str = "voucher"
    DISPATCH_SECTION: str = "partner"
    DISPATCH_OBJECT: str = "queries"
    DISPATCH_PARAM1: str = "163"
    DISPATCH_PARAM2: str = "save"
    DISPATCH_FORM_ID: int = 163
    DISPATCH_RETURN_FIELD: str = "q_number"
    DISPATCH_AGENT_LOGIN: str = ""
    DISPATCH_AGENT_PASS: str = ""
    DISPATCH_TOURAGENT_NAME: str = "ADIYA TRAVEL"
    DISPATCH_TOURAGENT_BIN: str = ""
    DISPATCH_DEFAULT_AIRLINE: str = "DV"
    DISPATCH_DEFAULT_DOC_PRODUCTION: str = "MIA OF RK"

    class Config:
        env_file = ".env"
        case_sensitive = True


# Создаём глобальный instance настроек
settings = Settings()
