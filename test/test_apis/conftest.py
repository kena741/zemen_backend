"""Fixtures for API integration tests (HTTP controllers and endpoints)."""

from __future__ import annotations

from typing import Any
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from app.api import create_app
from app.core.security.admin_deps import AdminContext, get_admin_context
from app.persistence.sqlalchemy.deps import get_db


class ApiTestDbSession:
    """Mock database session providing controllable query results."""

    def __init__(self, scalar_return: Any = None, scalars_return: list[Any] | None = None) -> None:
        self.scalar_return = scalar_return
        self.scalars_return = scalars_return or []
        self.statements: list[Any] = []
        self.added: list[Any] = []

    def add(self, entity: Any) -> None:
        self.added.append(entity)

    async def flush(self) -> None:
        pass

    async def commit(self) -> None:
        pass

    async def rollback(self) -> None:
        pass

    async def execute(self, stmt: Any) -> Any:
        self.statements.append(stmt)
        return self

    def scalar_one_or_none(self) -> Any:
        return self.scalar_return

    def scalar_one(self) -> Any:
        return self.scalar_return

    def scalars(self) -> Any:
        return self

    def all(self) -> list[Any]:
        return self.scalars_return


@pytest.fixture
def api_client():
    """Create a TestClient with customizable dependency overrides."""

    def _make_client(
        admin_context: AdminContext | None = None,
        db_session: Any | None = None,
    ) -> TestClient:
        app = create_app()

        if admin_context is not None:
            app.dependency_overrides[get_admin_context] = lambda: admin_context

        if db_session is not None:
            async def _override_db():
                yield db_session
            app.dependency_overrides[get_db] = _override_db

        return TestClient(app)

    return _make_client


@pytest.fixture
def super_admin_context() -> AdminContext:
    """Context for a super_admin with wildcard permissions."""
    return AdminContext(
        admin_id=uuid4(),
        user_id=uuid4(),
        email="superadmin@lolelink.com",
        full_name="Super Admin",
        role="super_admin",
        permissions=["*"],
    )


@pytest.fixture
def viewer_admin_context() -> AdminContext:
    """Context for a viewer admin with read-only permissions."""
    return AdminContext(
        admin_id=uuid4(),
        user_id=uuid4(),
        email="viewer@lolelink.com",
        full_name="Viewer Staff",
        role="viewer",
        permissions=[
            "providers:read",
            "services:read",
            "catalog:read",
            "bookings:read",
            "customers:read",
            "notifications:read",
            "finance:read",
            "contact:read",
            "documents:read",
            "settings:read",
        ],
    )
