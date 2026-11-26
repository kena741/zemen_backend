"""Unit tests for global API and database exception handlers."""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from pydantic import BaseModel
from sqlalchemy.exc import (
    DataError,
    IntegrityError,
    OperationalError,
    SQLAlchemyError,
    TimeoutError as SQLAlchemyTimeoutError,
)

from app.api.exception_handler import register_exception_handlers


class _ValidationPayload(BaseModel):
    phone: str


def _build_test_app() -> FastAPI:
    app = FastAPI()
    register_exception_handlers(app)

    @app.post("/validate")
    async def validate_endpoint(body: _ValidationPayload):
        return {"ok": True}

    @app.get("/db/unique")
    async def db_unique():
        orig = SimpleNamespace(sqlstate="23505")
        raise IntegrityError("INSERT INTO users ...", {}, orig)  # type: ignore[arg-type]

    @app.get("/db/fk")
    async def db_fk():
        orig = SimpleNamespace(pgcode="23503")
        raise IntegrityError("INSERT INTO bookings ...", {}, orig)  # type: ignore[arg-type]

    @app.get("/db/notnull")
    async def db_notnull():
        orig = SimpleNamespace(sqlstate="23502")
        raise IntegrityError("INSERT INTO bookings ...", {}, orig)  # type: ignore[arg-type]

    @app.get("/db/integrity-other")
    async def db_integrity_other():
        raise IntegrityError("INSERT INTO secret_table ...", {}, Exception("raw"))

    @app.get("/db/data")
    async def db_data():
        raise DataError("SELECT * FROM users WHERE id = 'bad'", {}, Exception("invalid input syntax"))

    @app.get("/db/operational")
    async def db_operational():
        raise OperationalError("SELECT 1", {}, Exception("connection refused"))

    @app.get("/db/timeout")
    async def db_timeout():
        raise SQLAlchemyTimeoutError("QueuePool limit overflow")

    @app.get("/db/generic")
    async def db_generic():
        raise SQLAlchemyError("SELECT secret_col FROM internal_table")

    @app.get("/boom")
    async def boom():
        raise RuntimeError("sensitive internal stack info")

    return app


@pytest.mark.asyncio
async def test_integrity_unique_returns_409_without_sql():
    app = _build_test_app()
    async with AsyncClient(transport=ASGITransport(app=app, raise_app_exceptions=False), base_url="http://test") as client:
        resp = await client.get("/db/unique")
    assert resp.status_code == 409
    body = resp.json()
    assert body["message"] == "Resource already exists or conflicts with an existing record."
    assert "INSERT INTO" not in resp.text


@pytest.mark.asyncio
async def test_integrity_fk_returns_400_without_sql():
    app = _build_test_app()
    async with AsyncClient(transport=ASGITransport(app=app, raise_app_exceptions=False), base_url="http://test") as client:
        resp = await client.get("/db/fk")
    assert resp.status_code == 400
    assert resp.json()["message"] == "Referenced resource does not exist."
    assert "bookings" not in resp.text


@pytest.mark.asyncio
async def test_integrity_notnull_returns_422():
    app = _build_test_app()
    async with AsyncClient(transport=ASGITransport(app=app, raise_app_exceptions=False), base_url="http://test") as client:
        resp = await client.get("/db/notnull")
    assert resp.status_code == 422
    assert resp.json()["message"] == "Missing required field."


@pytest.mark.asyncio
async def test_integrity_fallback_returns_409_without_sql():
    app = _build_test_app()
    async with AsyncClient(transport=ASGITransport(app=app, raise_app_exceptions=False), base_url="http://test") as client:
        resp = await client.get("/db/integrity-other")
    assert resp.status_code == 409
    assert "secret_table" not in resp.text


@pytest.mark.asyncio
async def test_data_error_returns_400():
    app = _build_test_app()
    async with AsyncClient(transport=ASGITransport(app=app, raise_app_exceptions=False), base_url="http://test") as client:
        resp = await client.get("/db/data")
    assert resp.status_code == 400
    assert resp.json()["message"] == "Invalid data format."
    assert "invalid input syntax" not in resp.text


@pytest.mark.asyncio
@pytest.mark.parametrize("path", ["/db/operational", "/db/timeout"])
async def test_db_unavailable_returns_503(path: str):
    app = _build_test_app()
    async with AsyncClient(transport=ASGITransport(app=app, raise_app_exceptions=False), base_url="http://test") as client:
        resp = await client.get(path)
    assert resp.status_code == 503
    assert resp.json()["message"] == "Database service temporarily unavailable."
    assert "connection refused" not in resp.text
    assert "QueuePool" not in resp.text


@pytest.mark.asyncio
async def test_generic_sqlalchemy_error_returns_500_without_sql():
    app = _build_test_app()
    async with AsyncClient(transport=ASGITransport(app=app, raise_app_exceptions=False), base_url="http://test") as client:
        resp = await client.get("/db/generic")
    assert resp.status_code == 500
    assert resp.json()["message"] == "An unexpected database error occurred."
    assert "secret_col" not in resp.text


@pytest.mark.asyncio
async def test_unhandled_exception_does_not_leak_detail_in_production(monkeypatch):
    from app.config import EnvironmentOptions, settings

    monkeypatch.setattr(settings, "ENVIRONMENT", EnvironmentOptions.PRODUCTION)
    app = _build_test_app()
    async with AsyncClient(transport=ASGITransport(app=app, raise_app_exceptions=False), base_url="http://test") as client:
        resp = await client.get("/boom")
    assert resp.status_code == 500
    body = resp.json()
    assert body == {"message": "Internal Server Error", "details": {}}
    assert "sensitive internal stack info" not in resp.text


@pytest.mark.asyncio
async def test_unhandled_exception_includes_detail_in_non_production(monkeypatch):
    from app.config import EnvironmentOptions, settings

    monkeypatch.setattr(settings, "ENVIRONMENT", EnvironmentOptions.DEVELOPMENT)
    app = _build_test_app()
    async with AsyncClient(transport=ASGITransport(app=app, raise_app_exceptions=False), base_url="http://test") as client:
        resp = await client.get("/boom")
    assert resp.status_code == 500
    body = resp.json()
    assert body["message"] == "Internal Server Error"
    assert body["details"]["detail"] == "sensitive internal stack info"


def test_wallet_transaction_out_accepts_decimal_amount():
    from decimal import Decimal
    from types import SimpleNamespace
    from uuid import uuid4

    from app.api.v1.schemas.wallet import WalletTransactionOut

    row = SimpleNamespace(
        id=uuid4(),
        amount=Decimal("125.00"),
        created_date=None,
        is_credit=True,
        note="Deposit",
        payment_type="chapa",
        transaction_id="tx_1",
        type="credit",
        user_id=uuid4(),
        provider_id=None,
        customer_id=uuid4(),
    )
    out = WalletTransactionOut.model_validate(row)
    assert out.amount == Decimal("125.00")


@pytest.mark.asyncio
async def test_request_validation_error_uses_unified_envelope():
    app = _build_test_app()
    async with AsyncClient(transport=ASGITransport(app=app, raise_app_exceptions=False), base_url="http://test") as client:
        resp = await client.post("/validate", json={})
    assert resp.status_code == 422
    body = resp.json()
    assert "message" in body
    assert "errors" in body["details"]
    assert body["details"]["errors"][0]["field"] == "phone"
