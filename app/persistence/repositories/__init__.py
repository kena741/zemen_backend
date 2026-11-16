"""Repository layer for database interaction and persistence."""

from app.persistence.repositories.base import BaseRepository
from app.persistence.repositories.telegram_repo import TelegramRepository

__all__ = ["BaseRepository", "TelegramRepository"]
