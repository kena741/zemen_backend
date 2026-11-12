"""Fixtures for Repository layer integration and unit tests."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest


class RepoMockSession:
    """Mock session simulating SQLAlchemy execution for repository queries."""

    def __init__(self, scalar_one_or_none_value: Any = None, scalars_value: list[Any] | None = None) -> None:
        self.scalar_value = scalar_one_or_none_value
        self.scalars_list = scalars_value or []
        self.executed_statements: list[Any] = []
        self.added_items: list[Any] = []
        self.rowcount = 1

    def add(self, item: Any) -> None:
        self.added_items.append(item)

    async def flush(self) -> None:
        pass

    async def execute(self, stmt: Any) -> Any:
        self.executed_statements.append(stmt)
        return self

    def scalar_one_or_none(self) -> Any:
        return self.scalar_value

    def scalar_one(self) -> Any:
        return self.scalar_value

    def scalars(self) -> Any:
        return self

    def all(self) -> list[Any]:
        return self.scalars_list


@pytest.fixture
def repo_session() -> RepoMockSession:
    return RepoMockSession()
