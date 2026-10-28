"""Chat writes on the same `chat` / `chat_inbox` rows Realtime already streams.

Inserting `chat` fires `manage_chat_inbox` (two directional inbox rows).
Deletes/seen are not covered by that trigger, so those paths update inbox here.
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from fastapi import HTTPException, status
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security.deps import AuthContext
from app.persistence.sqlalchemy.models import ChatInbox, ChatMessage

ALLOWED_TYPES = frozenset({"text", "image", "video", "audio", "file"})


def actor_ids(ctx: AuthContext) -> set[str]:
    ids = {str(ctx.user_id)}
    if ctx.customer_id is not None:
        ids.add(str(ctx.customer_id))
    if ctx.provider_id is not None:
        ids.add(str(ctx.provider_id))
    if ctx.handyman_id is not None:
        ids.add(str(ctx.handyman_id))
    return ids


def resolve_sender(ctx: AuthContext, requested: str | None) -> str:
    mine = actor_ids(ctx)
    if requested:
        sender = requested.strip()
        if sender not in mine:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")
        return sender
    if ctx.customer_id is not None and ctx.provider_id is None:
        return str(ctx.customer_id)
    if ctx.provider_id is not None and ctx.customer_id is None:
        return str(ctx.provider_id)
    return str(ctx.user_id)


def _inbox_ids(user_a: str, user_b: str) -> set[str]:
    ids = {f"{user_a}_{user_b}", f"{user_b}_{user_a}"}
    parts = sorted([user_a, user_b])
    ids.add(f"{parts[0]}_{parts[1]}")
    return ids


def _between(actor: set[str], peer: str):
    return or_(
        (ChatMessage.sender_id.in_(actor)) & (ChatMessage.receiver_id == peer),
        (ChatMessage.sender_id == peer) & (ChatMessage.receiver_id.in_(actor)),
    )


async def list_inbox(db: AsyncSession, *, ctx: AuthContext, limit: int = 50, offset: int = 0) -> list[ChatInbox]:
    mine = actor_ids(ctx)
    stmt = (
        select(ChatInbox)
        .where(or_(ChatInbox.sender_id.in_(mine), ChatInbox.receiver_id.in_(mine)))
        .order_by(ChatInbox.timestamp.desc())
        .limit(min(limit, 100))
        .offset(max(offset, 0))
    )
    return list((await db.execute(stmt)).scalars().all())


async def list_messages(
    db: AsyncSession, *, ctx: AuthContext, peer_id: str, limit: int = 50, offset: int = 0
) -> list[ChatMessage]:
    peer = peer_id.strip()
    if not peer:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="peer is required")
    stmt = (
        select(ChatMessage)
        .where(_between(actor_ids(ctx), peer))
        .order_by(ChatMessage.timestamp.desc())
        .limit(min(limit, 100))
        .offset(max(offset, 0))
    )
    return list((await db.execute(stmt)).scalars().all())


async def send_message(
    db: AsyncSession,
    *,
    ctx: AuthContext,
    peer_id: str,
    sender_id: str | None,
    message: str | None,
    media_url: str | None,
    msg_type: str,
    chat_id: str | None,
) -> ChatMessage:
    peer = peer_id.strip()
    sender = resolve_sender(ctx, sender_id)
    if not peer:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="receiver is required")
    if peer == sender or peer in actor_ids(ctx):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot message yourself")
    kind = (msg_type or "text").strip().lower() or "text"
    if kind not in ALLOWED_TYPES:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid message type")
    text = (message or "").strip()
    media = (media_url or "").strip()
    if not text and not media:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="message or mediaUrl is required")
    now = datetime.now(UTC)
    row = ChatMessage(
        chat_id=chat_id.strip() if chat_id and chat_id.strip() else str(uuid4()),
        type=kind,
        sender_id=sender,
        receiver_id=peer,
        message=text or None,
        media_url=media or None,
        seen=False,
        timestamp=now,
        created_at=now,
        updated_at=now,
    )
    db.add(row)
    await db.flush()
    await db.refresh(row)
    return row


async def mark_seen(db: AsyncSession, *, ctx: AuthContext, peer_id: str) -> int:
    peer = peer_id.strip()
    mine = actor_ids(ctx)
    if not peer:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="peer is required")
    rows = list(
        (
            await db.execute(
                select(ChatMessage).where(
                    ChatMessage.sender_id == peer,
                    ChatMessage.receiver_id.in_(mine),
                    ChatMessage.seen.is_(False),
                )
            )
        ).scalars().all()
    )
    for row in rows:
        row.seen = True
    inbox_ids: set[str] = set()
    for identity in mine:
        inbox_ids |= _inbox_ids(identity, peer)
    inboxes = list((await db.execute(select(ChatInbox).where(ChatInbox.id.in_(inbox_ids)))).scalars().all())
    for inbox in inboxes:
        inbox.seen = True
    await db.flush()
    return len(rows)


async def _latest_between(db: AsyncSession, mine: set[str], peer: str) -> ChatMessage | None:
    return (
        await db.execute(
            select(ChatMessage).where(_between(mine, peer)).order_by(ChatMessage.timestamp.desc()).limit(1)
        )
    ).scalar_one_or_none()


async def _delete_inbox_rows(db: AsyncSession, mine: set[str], peer: str) -> None:
    ids: set[str] = set()
    for identity in mine:
        ids |= _inbox_ids(identity, peer)
    rows = list((await db.execute(select(ChatInbox).where(ChatInbox.id.in_(ids)))).scalars().all())
    also = list(
        (
            await db.execute(
                select(ChatInbox).where(
                    or_(
                        (ChatInbox.sender_id.in_(mine)) & (ChatInbox.receiver_id == peer),
                        (ChatInbox.sender_id == peer) & (ChatInbox.receiver_id.in_(mine)),
                    )
                )
            )
        ).scalars().all()
    )
    seen: set[str] = set()
    for row in rows + also:
        if row.id in seen:
            continue
        seen.add(row.id)
        await db.delete(row)


async def _sync_inbox_after_delete(db: AsyncSession, mine: set[str], peer: str) -> None:
    latest = await _latest_between(db, mine, peer)
    if latest is None:
        await _delete_inbox_rows(db, mine, peer)
        return
    ids: set[str] = set()
    for identity in mine:
        ids |= _inbox_ids(identity, peer)
    rows = list((await db.execute(select(ChatInbox).where(ChatInbox.id.in_(ids)))).scalars().all())
    for row in rows:
        row.last_message = latest.message
        row.media_url = latest.media_url
        row.sender_id = latest.sender_id
        row.receiver_id = latest.receiver_id
        row.seen = latest.seen
        row.type = latest.type
        row.timestamp = latest.timestamp


async def delete_message(db: AsyncSession, *, ctx: AuthContext, peer_id: str, chat_id: str) -> ChatMessage:
    peer = peer_id.strip()
    mine = actor_ids(ctx)
    row = (
        await db.execute(select(ChatMessage).where(ChatMessage.chat_id == chat_id))
    ).scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Message not found")
    participants = {row.sender_id, row.receiver_id}
    if not participants & mine:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")
    if peer and peer not in participants:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Message not found")
    await db.delete(row)
    await _sync_inbox_after_delete(db, mine, peer or next(iter(participants - mine), row.receiver_id))
    await db.flush()
    return row


async def clear_conversation(db: AsyncSession, *, ctx: AuthContext, peer_id: str) -> int:
    peer = peer_id.strip()
    mine = actor_ids(ctx)
    if not peer:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="peer is required")
    rows = list((await db.execute(select(ChatMessage).where(_between(mine, peer)))).scalars().all())
    for row in rows:
        await db.delete(row)
    await _delete_inbox_rows(db, mine, peer)
    await db.flush()
    return len(rows)
