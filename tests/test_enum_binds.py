from sqlalchemy import update
from sqlalchemy.dialects.postgresql import asyncpg

from app.persistence.sqlalchemy.models import BookedService, JobRequest, Payment, Provider, Service


def _sql(stmt) -> str:
    return str(stmt.compile(dialect=asyncpg.dialect()))


def test_enum_columns_bind_as_their_postgres_type_not_varchar():
    assert "$1::status" in _sql(update(BookedService).values(status="accepted"))
    assert "::payment_status_enum" in _sql(update(BookedService).values(payment_status="pending_payment"))
    assert "::payment_status_enum" in _sql(update(Payment).values(status="payment_completed"))
    assert "::feature_request_status_enum" in _sql(update(Service).values(feature_requested_status="none"))
    assert "::feature_request_status_enum" in _sql(update(JobRequest).values(status="pending"))
    assert "::provider_type" in _sql(update(Provider).values(provider_type="company"))
    assert "::company_verification_status" in _sql(
        update(Provider).values(company_verification_status="pending")
    )
