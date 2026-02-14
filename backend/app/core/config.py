"""
Configuration settings
"""
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import List


class Settings(BaseSettings):
    """Настройки приложения"""

    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=True,
        extra="ignore",
    )

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
    DISPATCH_DRY_RUN: bool = False
    DISPATCH_TARGET_URL: str = ""  # legacy fallback for save URL
    DISPATCH_AUTH_URL: str = ""
    DISPATCH_SAVE_URL: str = ""
    DISPATCH_REQUEST_TIMEOUT_SECONDS: int = 30
    DISPATCH_MAX_ATTEMPTS: int = 5
    DISPATCH_RETRY_DELAY_SECONDS: int = 60
    DISPATCH_QUEUE_NAME: str = "tour_dispatch"

    # External payload defaults
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
    DISPATCH_DEFAULT_AIRLINE: str = "KC"
    DISPATCH_DEFAULT_DOC_PRODUCTION: str = "Ministry Of Internal Affairs"
    DISPATCH_DEFAULT_DOC_TYPE: str = "паспорт"
    DISPATCH_DEFAULT_RESIDENT: str = "резидент"
    DISPATCH_DEFAULT_BIRTH_DATE: str = "1970-01-01"
    DISPATCH_CLIENT_NAME_TEMPLATE: str = "Client_$CID"

    # Form fields for partner queries/163/save
    DISPATCH_FILIAL_ID: str = ""
    DISPATCH_FIRM_ID: str = ""
    DISPATCH_FIRM_NAME: str = ""
    DISPATCH_Q_INTERNAL: str = "1"
    DISPATCH_Q_AGENT_ASSIGN: str = "0"
    DISPATCH_Q_CURRENCY: str = "MRP"
    DISPATCH_Q_NUMBER_TEMPLATE: str = ""
    DISPATCH_OFFER_COUNTER: int = 0

    # Auth form details
    DISPATCH_AUTH_JUMP2: str = "/Voucher/partner/home"
    DISPATCH_AUTH_SUBMIT: str = "Вход"
    DISPATCH_USER_AGENT: str = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/143.0.0.0 Safari/537.36 Edg/143.0.0.0"
    )
    DISPATCH_ORIGIN: str = "https://report.fondkamkor.kz"
    DISPATCH_AUTH_REFERER: str = "https://report.fondkamkor.kz/Voucher/partner/auth"
    DISPATCH_SAVE_REFERER: str = "https://report.fondkamkor.kz/Voucher/partner/addquery/touroperator"

# Создаём глобальный instance настроек
settings = Settings()
