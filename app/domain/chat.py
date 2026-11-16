"""Domain models for Realtime Chat messages and User Inboxes."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


@dataclass
class ChatMessageDomain:
    chat_id: str
    sender_id: str
    receiver_id: str
    message: str | None = None
    media_url: str | None = None
    seen: bool = False
    type: str | None = "text"
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class ChatInboxDomain:
    id: str
    sender_id: str
    receiver_id: str
    last_message: str | None = None
    media_url: str | None = None
    seen: bool = False
    type: str | None = "text"
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    archive: bool = False
    peer_name: str | None = None
    peer_image: str | None = None

