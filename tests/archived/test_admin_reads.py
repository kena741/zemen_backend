import asyncio
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.api import create_app
from app.api.v1.schemas.admin_reads import AdminCustomerOut, AdminProviderOut
from app.core.security.admin_deps import AdminContext, get_admin_context
from app.core.services.admin_reads import _like, dashboard_summary


class _Res:
    def all(self):
        return []

    def one(self):
        return (0, 0)

    def scalar_one(self):
        return 0


class _RecordingDb:
    def __init__(self):
        self.calls = 0

    async def execute(self, _stmt):
        self.calls += 1
        return _Res()


def _client(permissions: list[str]) -> TestClient:
    app = create_app()
    app.dependency_overrides[get_admin_context] = lambda: AdminContext(
        admin_id=uuid4(), user_id=uuid4(), email=None, full_name=None, role="custom", permissions=permissions
    )
    return TestClient(app)


def test_dashboard_only_includes_permitted_sections():
    db = _RecordingDb()
    out = asyncio.run(dashboard_summary(db, lambda p: p == "bookings:read"))
    assert set(out) == {"bookings_by_status", "bookings"}
    assert db.calls == 2


def test_dashboard_with_no_permissions_runs_no_queries():
    db = _RecordingDb()
    assert asyncio.run(dashboard_summary(db, lambda p: False)) == {}
    assert db.calls == 0


def test_search_escapes_like_wildcards():
    assert _like("50%_off") == "%50\\%\\_off%"


def test_admin_dtos_do_not_expose_push_tokens():
    assert "fcm_token" not in AdminCustomerOut.model_fields
    assert "fcm_token" not in AdminProviderOut.model_fields


@pytest.mark.parametrize(
    ("path", "needs"),
    [
        ("/api/v1/admin/customers", "customers:read"),
        ("/api/v1/admin/providers", "providers:read"),
        (f"/api/v1/admin/providers/{uuid4()}", "providers:read"),
        ("/api/v1/admin/services", "services:read"),
        ("/api/v1/admin/bookings", "bookings:read"),
        (f"/api/v1/admin/bookings/{uuid4()}", "bookings:read"),
        ("/api/v1/admin/withdrawals", "finance:read"),
        (f"/api/v1/admin/withdrawals/{uuid4()}", "finance:read"),
        ("/api/v1/admin/finance/reconciliation", "finance:read"),
    ],
)
def test_reads_require_matching_permission(path, needs):
    others = [p for p in ("customers:read", "providers:read", "services:read", "bookings:read", "finance:read") if p != needs]
    assert _client(others).get(path).status_code == 403


def test_invalid_enum_filter_is_rejected_before_db():
    client = _client(["bookings:read", "finance:read"])
    assert client.get("/api/v1/admin/bookings", params={"status": "done"}).status_code == 422
    assert client.get("/api/v1/admin/withdrawals", params={"status": "paid"}).status_code == 422


class _Row:
    def __init__(self, **kw):
        self._mapping = kw


class _ReconResult:
    def __init__(self, rows):
        self._rows = rows

    def __iter__(self):
        return iter(self._rows)

    def one(self):
        return self._rows[0]


class _ReconDb:
    def __init__(self, results):
        self._results = list(results)
        self.statements: list[str] = []

    async def execute(self, stmt, _params=None):
        self.statements.append(str(stmt).lower())
        return _ReconResult(self._results.pop(0))


def test_reconciliation_is_read_only_and_rounds_money():
    from decimal import Decimal

    from app.api.v1.schemas.admin_reads import ReconciliationReport
    from app.core.services.finance_reconciliation import reconciliation_report

    acct = uuid4()
    health = _Row(
        total_rows=3, non_numeric_amounts=0, untyped_rows=0,
        orphan_customer_rows=0, orphan_provider_rows=0, non_numeric_provider_balances=0,
    )
    db = _ReconDb([
        [_Row(transaction_id="b1", type="provider", amount="5.56", note="refund", copies=3,
              first_at=None, last_at=None, excess_amount=Decimal("11.12"))],
        [_Row(account_id=acct, balance=Decimal("10.004999"), ledger_net=Decimal("4"),
              drift=Decimal("6.004999"), ledger_rows=2)],
        [_Row(account_id=uuid4(), balance=Decimal("0"), ledger_net=Decimal("2.5"),
              drift=Decimal("-2.5"), ledger_rows=1)],
        [health],
    ])
    out = asyncio.run(reconciliation_report(db, limit=10))

    assert all(s.lstrip().startswith(("select", "with")) for s in db.statements)
    assert not any(w in s for s in db.statements for w in ("insert ", "update ", "delete ", "for update"))
    assert out["provider_drift"][0]["drift"] == Decimal("6.00")
    assert out["provider_drift_total"] == Decimal("6.00")
    assert out["customer_drift_total"] == Decimal("2.50")
    assert out["duplicate_excess_total"] == Decimal("11.12")
    body = ReconciliationReport.model_validate(out).model_dump(by_alias=True)
    assert body["providerDrift"][0]["accountId"] == acct
