import asyncio
from types import SimpleNamespace
from uuid import uuid4

from fastapi.testclient import TestClient

from app.api import create_app
from app.core.services.catalog_service import list_sub_category_documents
from app.persistence.sqlalchemy.deps import get_db


class _Rows:
    def __init__(self, rows):
        self._rows = rows

    def all(self):
        return self._rows

    def scalars(self):
        return self

    def scalar_one_or_none(self):
        return self._rows[0] if self._rows else None


class _Db:
    def __init__(self, rows):
        self.rows = rows
        self.statements = []

    async def execute(self, stmt):
        self.statements.append(stmt)
        return _Rows(self.rows)


def _client(rows) -> TestClient:
    app = create_app()

    async def _db():
        yield _Db(rows)

    app.dependency_overrides[get_db] = _db
    return TestClient(app)


def test_active_currency_is_null_when_none_configured():
    res = _client([]).get("/api/v1/config/currency")
    assert res.status_code == 200
    assert res.json() is None


def test_currency_uses_app_field_names():
    row = SimpleNamespace(
        id=1, active=True, name="Birr", symbol="ETB", decimal_digits="2", symbol_at_right=True, created_at=None
    )
    body = _client([row]).get("/api/v1/config/currencies").json()
    assert body[0]["decimalDigits"] == "2"
    assert body[0]["symbolAtRight"] is True


def test_languages_are_public():
    row = SimpleNamespace(id=uuid4(), active=True, code="am", name="Amharic")
    assert _client([row]).get("/api/v1/config/languages").json()[0]["code"] == "am"


def test_sub_category_documents_dedupe_and_treat_null_as_required():
    doc = SimpleNamespace(id=uuid4(), name="ID", description=None, active=True)
    other = SimpleNamespace(id=uuid4(), name="License", description=None, active=True)
    db = _Db([(doc, "front side", None), (doc, "duplicate link", True), (other, None, True)])

    out = asyncio.run(list_sub_category_documents(db, uuid4()))

    assert [(d.id, desc, req) for d, desc, req in out] == [
        (doc.id, "front side", True),
        (other.id, None, True),
    ]
    assert "IS NOT false" in str(db.statements[0].compile(compile_kwargs={"literal_binds": True}))


def test_sub_category_documents_response_shape():
    doc = SimpleNamespace(id=uuid4(), name="ID", description="National ID", active=True)
    body = _client([(doc, "both sides", True)]).get(
        f"/api/v1/catalog/sub-categories/{uuid4()}/documents"
    ).json()
    assert body == [
        {
            "document": {"id": str(doc.id), "name": "ID", "description": "National ID", "active": True},
            "description": "both sides",
            "isRequired": True,
        }
    ]
