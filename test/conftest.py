"""Root pytest configuration and shared fixtures for the test/ suite."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncGenerator
from typing import Any
from uuid import UUID, uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth.jwt import create_access_token


class MockDbSession:
    """Lightweight AsyncSession mock for unit testing repository and service layers."""

    def __init__(self, execute_result: Any = None) -> None:
        self._execute_result = execute_result
        self.added: list[Any] = []
        self.deleted: list[Any] = []
        self.statements: list[Any] = []

    def add(self, instance: Any) -> None:
        self.added.append(instance)

    async def flush(self) -> None:
        pass

    async def commit(self) -> None:
        pass

    async def rollback(self) -> None:
        pass

    async def execute(self, stmt: Any) -> Any:
        self.statements.append(stmt)
        return self._execute_result


@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for each test case."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def mock_db_session() -> MockDbSession:
    return MockDbSession()


@pytest.fixture
def make_admin_token():
    """Helper fixture to generate signed admin JWTs for tests."""

    def _generate(
        user_id: UUID | None = None,
        email: str = "admin@example.com",
        role: str = "super_admin",
    ) -> str:
        uid = user_id or uuid4()
        return create_access_token(
            user_id=uid,
            email=email,
            role="authenticated",
            extra_claims={"admin_role": role},
        )

    return _generate
