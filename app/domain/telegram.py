"""Domain models for Telegram chat, leaderboard, and invite statistics."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone


@dataclass
class TelegramChatDomain:
    chat_id: int
    title: str | None = None
    type: str = "group"
    is_active: bool = True
    total_members: int = 0
    total_invites: int = 0
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class TelegramLeaderboardDomain:
    user_id: int
    username: str | None = None
    first_name: str = ""
    total_invites: int = 0


@dataclass
class TelegramInviteStatDomain:
    chat_id: int
    user_id: int
    total_invites: int = 0
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
