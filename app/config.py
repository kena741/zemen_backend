from enum import Enum
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT_DIR = Path(__file__).resolve().parent.parent
load_dotenv(ROOT_DIR / ".env")


class EnvironmentOptions(str, Enum):
    DEVELOPMENT = "development"
    STAGING = "staging"
    PRODUCTION = "production"

    @classmethod
    def _missing_(cls, value: object) -> "EnvironmentOptions | None":
        if isinstance(value, int):
            int_map = {
                1: cls.DEVELOPMENT,
                2: cls.STAGING,
                4: cls.PRODUCTION,
            }
            if value in int_map:
                return int_map[value]
        if isinstance(value, str):
            clean = value.strip().lower()
            str_map = {
                "1": cls.DEVELOPMENT,
                "dev": cls.DEVELOPMENT,
                "development": cls.DEVELOPMENT,
                "local": cls.DEVELOPMENT,
                "2": cls.STAGING,
                "stage": cls.STAGING,
                "staging": cls.STAGING,
                "4": cls.PRODUCTION,
                "prod": cls.PRODUCTION,
                "production": cls.PRODUCTION,
            }
            if clean in str_map:
                return str_map[clean]
        return None


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    ENVIRONMENT: EnvironmentOptions = EnvironmentOptions.DEVELOPMENT

    # Environment-specific Database URLs
    DEVELOPMENT_DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/zemen_db"
    STAGING_DATABASE_URL: str | None = None
    PRODUCTION_DATABASE_URL: str | None = None

    # Backward compatibility aliases
    DEV_DATABASE_URL: str | None = None
    PROD_DATABASE_URL: str | None = None

    # Active Database URL (resolved and assigned based on ENVIRONMENT)
    DATABASE_URL: str | None = None

    # Connection pool configuration
    DATABASE_POOL_SIZE: int | None = None
    DATABASE_POOL_OVERFLOW: int | None = None
    DATABASE_POOL_RECYCLE: int = 1800
    DATABASE_POOL_TIMEOUT: int = 30
    DATABASE_ECHO: bool = False

    CORS_ALLOWED_ORIGINS: list[str] = ["*"]

    SUPABASE_URL: str = "https://rffptyqhqvzrpmyxlwwu.supabase.co"
    SUPABASE_ANON_KEY: str = ""
    SUPABASE_JWT_SECRET: str = ""
    SUPABASE_JWT_AUDIENCE: str = "authenticated"
    SUPABASE_JWT_USE_JWKS: bool = False
    SUPABASE_SERVICE_ROLE_KEY: str = ""

    # Plan 4: money writes stay off until ledger parity + Edge cutover.
    PAYMENTS_WRITES_ENABLED: bool = False
    CHAPA_SECRET_KEY: str = ""
    CHAPA_VERIFY_URL: str = "https://api.chapa.co/v1/transaction/verify"

    # Custom Auth (JWT)
    JWT_SECRET_KEY: str = "insecure-change-me-in-production-jwt-secret-key-32chars"
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    JWT_REFRESH_TOKEN_EXPIRE_DAYS: int = 30

    # Google Cloud Storage (GCS)
    GCS_PROJECT_ID: str | None = None
    GCS_CREDENTIALS_JSON: str | None = None
    GCS_CREDENTIALS_FILE: str | None = None
    GCS_DEFAULT_BUCKET: str = "betegnabucket"
    GCS_ADMIN_DOCS_BUCKET: str = "admin-documents"
    GCS_FEEDBACK_BUCKET: str = "feedback"
    GCS_PUBLIC_URL_BASE: str = "https://storage.googleapis.com"

    # Firebase Cloud Messaging (FCM)
    FIREBASE_CREDENTIALS_JSON: str | None = None
    FIREBASE_CREDENTIALS_FILE: str | None = None

    # Telegram Bot Webhook Integration
    TELEGRAM_BOT_TOKEN: str = ""
    TELEGRAM_WEBHOOK_SECRET: str = ""
    TELEGRAM_WEBHOOK_URL: str = ""
    TELEGRAM_AUTO_REGISTER_WEBHOOK: bool = True

    @field_validator(
        "DATABASE_POOL_SIZE",
        "DATABASE_POOL_OVERFLOW",
        "DATABASE_URL",
        "STAGING_DATABASE_URL",
        "PRODUCTION_DATABASE_URL",
        "DEV_DATABASE_URL",
        "PROD_DATABASE_URL",
        mode="before",
    )
    @classmethod
    def empty_str_to_none(cls, v: Any) -> Any:
        if isinstance(v, str) and not v.strip():
            return None
        return v

    @field_validator("ENVIRONMENT", mode="before")
    @classmethod
    def parse_environment(cls, v: Any) -> EnvironmentOptions:
        if isinstance(v, EnvironmentOptions):
            return v
        try:
            matched = EnvironmentOptions(v)
            if matched is not None:
                return matched
        except (ValueError, TypeError):
            pass
        raise ValueError(
            f"Invalid environment '{v}'. Expected one of: "
            "development, staging, production."
        )

    @model_validator(mode="after")
    def resolve_database_configuration(self) -> "Settings":
        # 1. Filter and assign DATABASE_URL based on ENVIRONMENT
        if self.ENVIRONMENT == EnvironmentOptions.DEVELOPMENT:
            self.DATABASE_URL = (
                self.DEVELOPMENT_DATABASE_URL
                or self.DEV_DATABASE_URL
                or self.DATABASE_URL
                or "postgresql+asyncpg://postgres:postgres@localhost:5432/zemen_db"
            )
        elif self.ENVIRONMENT == EnvironmentOptions.STAGING:
            self.DATABASE_URL = (
                self.STAGING_DATABASE_URL
                or self.DATABASE_URL
            )
            if not self.DATABASE_URL:
                raise ValueError(
                    "STAGING_DATABASE_URL must be provided when running in staging environment."
                )
        elif self.ENVIRONMENT == EnvironmentOptions.PRODUCTION:
            self.DATABASE_URL = (
                self.PRODUCTION_DATABASE_URL
                or self.PROD_DATABASE_URL
                or self.DATABASE_URL
            )
            if not self.DATABASE_URL:
                raise ValueError(
                    "PRODUCTION_DATABASE_URL must be provided when running in production environment."
                )

        # 2. Environment-tuned connection pool defaults
        if self.DATABASE_POOL_SIZE is None:
            if self.ENVIRONMENT == EnvironmentOptions.DEVELOPMENT:
                self.DATABASE_POOL_SIZE = 5
            else:
                self.DATABASE_POOL_SIZE = 10

        if self.DATABASE_POOL_OVERFLOW is None:
            if self.ENVIRONMENT == EnvironmentOptions.DEVELOPMENT:
                self.DATABASE_POOL_OVERFLOW = 2
            else:
                self.DATABASE_POOL_OVERFLOW = 5

        return self

    @property
    def supabase_issuer(self) -> str:
        return f"{self.SUPABASE_URL.rstrip('/')}/auth/v1"

    @property
    def supabase_jwks_url(self) -> str:
        return f"{self.supabase_issuer}/.well-known/jwks.json"


settings = Settings()
