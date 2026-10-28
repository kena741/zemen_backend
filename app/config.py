from enum import IntEnum
from pathlib import Path

from dotenv import load_dotenv
from pydantic_settings import BaseSettings, SettingsConfigDict

load_dotenv(Path(__file__).resolve().parent.parent / ".env")


class EnvironmentOptions(IntEnum):
    DEVELOPMENT = 1
    STAGING = 2
    PRODUCTION = 4


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    ENVIRONMENT: EnvironmentOptions = EnvironmentOptions.DEVELOPMENT

    DATABASE_URL: str = "postgresql+asyncpg://postgres:password@localhost:5432/postgres"
    DATABASE_POOL_SIZE: int = 10
    DATABASE_POOL_OVERFLOW: int = 5
    DATABASE_POOL_RECYCLE: int = 1800
    DATABASE_POOL_TIMEOUT: int = 30

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

    @property
    def supabase_issuer(self) -> str:
        return f"{self.SUPABASE_URL.rstrip('/')}/auth/v1"

    @property
    def supabase_jwks_url(self) -> str:
        return f"{self.supabase_issuer}/.well-known/jwks.json"


settings = Settings()
