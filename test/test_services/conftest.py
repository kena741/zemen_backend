"""Fixtures for Service layer unit tests (mocked repositories)."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock

import pytest


class ServiceMockSession:
    def __init__(self) -> None:
        self.added: list[Any] = []
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
        return self


@pytest.fixture
def mock_audit_service():
    """Mock audit logging service to verify that operations record admin actions."""
    mock = AsyncMock()
    mock.log_action = AsyncMock(return_value=None)
    return mock
