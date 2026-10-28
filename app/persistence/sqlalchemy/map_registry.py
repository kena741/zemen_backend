"""Import ORM models so mappers are registered at app startup."""


def init_mapper() -> None:
    from app.persistence.sqlalchemy import models as _models  # noqa: F401

    _ = _models
