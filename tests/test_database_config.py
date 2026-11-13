import pytest
from app.config import EnvironmentOptions, Settings


def test_environment_options_string_values():
    assert EnvironmentOptions.DEVELOPMENT.value == "development"
    assert EnvironmentOptions.STAGING.value == "staging"
    assert EnvironmentOptions.PRODUCTION.value == "production"


def test_environment_parsing_from_strings():
    s_dev = Settings(
        ENVIRONMENT="development",
        DEVELOPMENT_DATABASE_URL="postgresql+asyncpg://dev:dev@localhost/dev",
    )
    assert s_dev.ENVIRONMENT == EnvironmentOptions.DEVELOPMENT
    assert s_dev.DATABASE_URL == "postgresql+asyncpg://dev:dev@localhost/dev"

    s_dev_short = Settings(
        ENVIRONMENT="dev",
        DEVELOPMENT_DATABASE_URL="postgresql+asyncpg://dev:dev@localhost/dev",
    )
    assert s_dev_short.ENVIRONMENT == EnvironmentOptions.DEVELOPMENT
    assert s_dev_short.DATABASE_URL == "postgresql+asyncpg://dev:dev@localhost/dev"

    s_stage = Settings(
        ENVIRONMENT="staging",
        STAGING_DATABASE_URL="postgresql+asyncpg://stage:stage@localhost/staging",
    )
    assert s_stage.ENVIRONMENT == EnvironmentOptions.STAGING
    assert s_stage.DATABASE_URL == "postgresql+asyncpg://stage:stage@localhost/staging"

    s_prod = Settings(
        ENVIRONMENT="production",
        PRODUCTION_DATABASE_URL="postgresql+asyncpg://prod:prod@localhost/prod",
    )
    assert s_prod.ENVIRONMENT == EnvironmentOptions.PRODUCTION
    assert s_prod.DATABASE_URL == "postgresql+asyncpg://prod:prod@localhost/prod"


def test_environment_parsing_from_ints():
    s_dev = Settings(ENVIRONMENT=1, DEVELOPMENT_DATABASE_URL="postgresql+asyncpg://dev:dev@localhost/dev")
    assert s_dev.ENVIRONMENT == EnvironmentOptions.DEVELOPMENT

    s_stage = Settings(ENVIRONMENT=2, STAGING_DATABASE_URL="postgresql+asyncpg://stage:stage@localhost/staging")
    assert s_stage.ENVIRONMENT == EnvironmentOptions.STAGING

    s_prod = Settings(ENVIRONMENT=4, PRODUCTION_DATABASE_URL="postgresql+asyncpg://prod:prod@localhost/prod")
    assert s_prod.ENVIRONMENT == EnvironmentOptions.PRODUCTION


def test_invalid_environment_raises():
    with pytest.raises(ValueError, match="Invalid environment"):
        Settings(ENVIRONMENT="invalid_env")


def test_database_url_filtering_by_environment():
    # When ENVIRONMENT=development -> DEVELOPMENT_DATABASE_URL is assigned to DATABASE_URL
    s_dev = Settings(
        ENVIRONMENT="development",
        DEVELOPMENT_DATABASE_URL="postgresql+asyncpg://dev_user:pass@localhost/dev_db",
        STAGING_DATABASE_URL="postgresql+asyncpg://stage_user:pass@stage_host/stage_db",
        PRODUCTION_DATABASE_URL="postgresql+asyncpg://prod_user:pass@prod_host/prod_db",
    )
    assert s_dev.DATABASE_URL == "postgresql+asyncpg://dev_user:pass@localhost/dev_db"
    assert s_dev.DATABASE_POOL_SIZE == 5
    assert s_dev.DATABASE_POOL_OVERFLOW == 2

    # When ENVIRONMENT=staging -> STAGING_DATABASE_URL is assigned to DATABASE_URL
    s_stage = Settings(
        ENVIRONMENT="staging",
        DEVELOPMENT_DATABASE_URL="postgresql+asyncpg://dev_user:pass@localhost/dev_db",
        STAGING_DATABASE_URL="postgresql+asyncpg://stage_user:pass@stage_host/stage_db",
        PRODUCTION_DATABASE_URL="postgresql+asyncpg://prod_user:pass@prod_host/prod_db",
    )
    assert s_stage.DATABASE_URL == "postgresql+asyncpg://stage_user:pass@stage_host/stage_db"
    assert s_stage.DATABASE_POOL_SIZE == 10
    assert s_stage.DATABASE_POOL_OVERFLOW == 5

    # When ENVIRONMENT=production -> PRODUCTION_DATABASE_URL is assigned to DATABASE_URL
    s_prod = Settings(
        ENVIRONMENT="production",
        DEVELOPMENT_DATABASE_URL="postgresql+asyncpg://dev_user:pass@localhost/dev_db",
        STAGING_DATABASE_URL="postgresql+asyncpg://stage_user:pass@stage_host/stage_db",
        PRODUCTION_DATABASE_URL="postgresql+asyncpg://prod_user:pass@prod_host/prod_db",
    )
    assert s_prod.DATABASE_URL == "postgresql+asyncpg://prod_user:pass@prod_host/prod_db"
    assert s_prod.DATABASE_POOL_SIZE == 10
    assert s_prod.DATABASE_POOL_OVERFLOW == 5


def test_production_missing_database_url_raises():
    with pytest.raises(ValueError, match="PRODUCTION_DATABASE_URL must be provided"):
        Settings(
            ENVIRONMENT="production",
            DATABASE_URL=None,
            PRODUCTION_DATABASE_URL=None,
            PROD_DATABASE_URL=None,
        )


def test_staging_missing_database_url_raises():
    with pytest.raises(ValueError, match="STAGING_DATABASE_URL must be provided"):
        Settings(
            ENVIRONMENT="staging",
            DATABASE_URL=None,
            STAGING_DATABASE_URL=None,
        )


def test_pool_size_explicit_override():
    s = Settings(
        ENVIRONMENT="development",
        DEVELOPMENT_DATABASE_URL="postgresql+asyncpg://dev:dev@localhost/dev",
        DATABASE_POOL_SIZE=25,
        DATABASE_POOL_OVERFLOW=12,
    )
    assert s.DATABASE_POOL_SIZE == 25
    assert s.DATABASE_POOL_OVERFLOW == 12


def test_telegram_config_environment_separation():
    # Staging resolution
    s_staging = Settings(
        ENVIRONMENT="staging",
        STAGING_DATABASE_URL="postgresql+asyncpg://stage:stage@localhost/staging",
        STAGING_TELEGRAM_BOT_TOKEN="staging-bot-token",
        STAGING_TELEGRAM_WEBHOOK_SECRET="staging-secret",
        STAGING_TELEGRAM_WEBHOOK_URL="https://staging.example.com/webhook",
    )
    assert s_staging.TELEGRAM_BOT_TOKEN == "staging-bot-token"
    assert s_staging.TELEGRAM_WEBHOOK_SECRET == "staging-secret"
    assert s_staging.TELEGRAM_WEBHOOK_URL == "https://staging.example.com/webhook"

    # Production resolution
    s_prod = Settings(
        ENVIRONMENT="production",
        PRODUCTION_DATABASE_URL="postgresql+asyncpg://prod:prod@localhost/prod",
        PRODUCTION_TELEGRAM_BOT_TOKEN="prod-bot-token",
        PRODUCTION_TELEGRAM_WEBHOOK_SECRET="prod-secret",
        PRODUCTION_TELEGRAM_WEBHOOK_URL="https://prod.example.com/webhook",
    )
    assert s_prod.TELEGRAM_BOT_TOKEN == "prod-bot-token"
    assert s_prod.TELEGRAM_WEBHOOK_SECRET == "prod-secret"
    assert s_prod.TELEGRAM_WEBHOOK_URL == "https://prod.example.com/webhook"

    # Fallback to direct TELEGRAM_BOT_TOKEN if env-specific is unset
    s_fallback = Settings(
        ENVIRONMENT="staging",
        STAGING_DATABASE_URL="postgresql+asyncpg://stage:stage@localhost/staging",
        TELEGRAM_BOT_TOKEN="generic-bot-token",
    )
    assert s_fallback.TELEGRAM_BOT_TOKEN == "generic-bot-token"

