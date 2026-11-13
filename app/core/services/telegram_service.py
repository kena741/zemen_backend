from datetime import datetime, timezone
import logging
from typing import Any

import httpx
from sqlalchemy import func, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.schemas.telegram import (
    ChatMemberUpdatedPayload,
    TelegramLeaderboardEntry,
    TelegramWebhookRegistrationResponse,
    TelegramWebhookUpdate,
)
from app.config import settings
from app.persistence.sqlalchemy.models.telegram import (
    TelegramChat,
    TelegramChatMember,
    TelegramInviteLink,
    TelegramInviteStat,
    TelegramUser,
)

logger = logging.getLogger(__name__)

JOIN_STATUSES = {"member", "administrator", "restricted"}
LEAVE_STATUSES = {"left", "kicked"}


async def register_webhook(
    bot_token: str | None = None,
    webhook_url: str | None = None,
    secret_token: str | None = None,
    allowed_updates: list[str] | None = None,
) -> TelegramWebhookRegistrationResponse:
    """Registers the webhook with Telegram Bot API with allowed_updates=["chat_member", "my_chat_member"]."""
    token = settings.TELEGRAM_BOT_TOKEN if bot_token is None else bot_token
    target_url = settings.TELEGRAM_WEBHOOK_URL if webhook_url is None else webhook_url
    secret = settings.TELEGRAM_WEBHOOK_SECRET if secret_token is None else secret_token

    if not token:
        logger.warning("Telegram Bot Token is not set; skipping webhook registration.")
        return TelegramWebhookRegistrationResponse(
            ok=False, description="TELEGRAM_BOT_TOKEN is not configured"
        )

    if not target_url:
        logger.warning("Telegram Webhook URL is not set; skipping webhook registration.")
        return TelegramWebhookRegistrationResponse(
            ok=False, description="TELEGRAM_WEBHOOK_URL is not configured"
        )

    updates = allowed_updates or ["chat_member", "my_chat_member"]

    url = f"https://api.telegram.org/bot{token}/setWebhook"
    payload: dict[str, Any] = {
        "url": target_url,
        "allowed_updates": updates,
        "drop_pending_updates": False,
    }
    if secret:
        payload["secret_token"] = secret

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(url, json=payload)
            data = resp.json()
            is_ok = bool(data.get("ok", False))
            description = data.get("description", "Webhook registered successfully" if is_ok else "Registration failed")
            if is_ok:
                logger.info(
                    "Telegram webhook registered successfully at %s with allowed_updates=%s",
                    target_url,
                    updates,
                )
            else:
                logger.error("Failed to register Telegram webhook: %s", description)
            return TelegramWebhookRegistrationResponse(
                ok=is_ok,
                description=description,
                url=target_url,
            )
    except Exception as exc:
        logger.exception("Exception occurred while registering Telegram webhook: %s", exc)
        return TelegramWebhookRegistrationResponse(
            ok=False,
            description=str(exc),
            url=target_url,
        )


async def delete_webhook(bot_token: str | None = None) -> TelegramWebhookRegistrationResponse:
    """Removes the Telegram webhook."""
    token = bot_token or settings.TELEGRAM_BOT_TOKEN
    if not token:
        return TelegramWebhookRegistrationResponse(
            ok=False, description="TELEGRAM_BOT_TOKEN is not configured"
        )

    url = f"https://api.telegram.org/bot{token}/deleteWebhook"
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(url, json={"drop_pending_updates": False})
            data = resp.json()
            return TelegramWebhookRegistrationResponse(
                ok=bool(data.get("ok", False)),
                description=data.get("description"),
            )
    except Exception as exc:
        logger.exception("Failed to delete Telegram webhook: %s", exc)
        return TelegramWebhookRegistrationResponse(ok=False, description=str(exc))


async def process_chat_member_updated(
    db: AsyncSession,
    event: ChatMemberUpdatedPayload,
) -> dict[str, Any]:
    """
    Parses a ChatMemberUpdated payload, records the event, and updates invite counts.
    Handles both direct additions (user added another) and invite link clicks.
    Guarantees idempotency to prevent duplicate increments on rejoins.
    """
    chat_payload = event.chat
    joining_user_payload = event.new_chat_member.user
    actor_payload = event.from_user
    old_status = event.old_chat_member.status
    new_status = event.new_chat_member.status
    event_timestamp = datetime.fromtimestamp(event.date, tz=timezone.utc)

    # 1. Upsert Telegram Chat
    chat_stmt = (
        insert(TelegramChat)
        .values(
            chat_id=chat_payload.id,
            title=chat_payload.title,
            type=chat_payload.type,
            is_active=True,
        )
        .on_conflict_do_update(
            index_elements=[TelegramChat.chat_id],
            set_={
                "title": chat_payload.title,
                "type": chat_payload.type,
                "is_active": True,
                "updated_at": func.now(),
            },
        )
    )
    await db.execute(chat_stmt)

    # 2. Upsert Joining User
    joining_user_stmt = (
        insert(TelegramUser)
        .values(
            user_id=joining_user_payload.id,
            username=joining_user_payload.username,
            first_name=joining_user_payload.first_name,
            last_name=joining_user_payload.last_name,
            is_bot=joining_user_payload.is_bot,
        )
        .on_conflict_do_update(
            index_elements=[TelegramUser.user_id],
            set_={
                "username": joining_user_payload.username,
                "first_name": joining_user_payload.first_name,
                "last_name": joining_user_payload.last_name,
                "is_bot": joining_user_payload.is_bot,
                "updated_at": func.now(),
            },
        )
    )
    await db.execute(joining_user_stmt)

    # 3. Upsert Actor User (if different from joining user)
    if actor_payload.id != joining_user_payload.id:
        actor_stmt = (
            insert(TelegramUser)
            .values(
                user_id=actor_payload.id,
                username=actor_payload.username,
                first_name=actor_payload.first_name,
                last_name=actor_payload.last_name,
                is_bot=actor_payload.is_bot,
            )
            .on_conflict_do_update(
                index_elements=[TelegramUser.user_id],
                set_={
                    "username": actor_payload.username,
                    "first_name": actor_payload.first_name,
                    "last_name": actor_payload.last_name,
                    "is_bot": actor_payload.is_bot,
                    "updated_at": func.now(),
                },
            )
        )
        await db.execute(actor_stmt)

    # 4. Upsert Link Creator User & Invite Link (if present)
    invite_link_str: str | None = None
    link_creator_id: int | None = None

    if event.invite_link:
        invite_link_str = event.invite_link.invite_link
        if event.invite_link.creator:
            link_creator_payload = event.invite_link.creator
            link_creator_id = link_creator_payload.id
            creator_stmt = (
                insert(TelegramUser)
                .values(
                    user_id=link_creator_payload.id,
                    username=link_creator_payload.username,
                    first_name=link_creator_payload.first_name,
                    last_name=link_creator_payload.last_name,
                    is_bot=link_creator_payload.is_bot,
                )
                .on_conflict_do_update(
                    index_elements=[TelegramUser.user_id],
                    set_={
                        "username": link_creator_payload.username,
                        "first_name": link_creator_payload.first_name,
                        "last_name": link_creator_payload.last_name,
                        "is_bot": link_creator_payload.is_bot,
                        "updated_at": func.now(),
                    },
                )
            )
            await db.execute(creator_stmt)

        link_stmt = (
            insert(TelegramInviteLink)
            .values(
                invite_link=invite_link_str,
                chat_id=chat_payload.id,
                creator_user_id=link_creator_id,
                name=event.invite_link.name,
                is_primary=event.invite_link.is_primary,
            )
            .on_conflict_do_update(
                index_elements=[TelegramInviteLink.invite_link],
                set_={
                    "name": event.invite_link.name,
                    "is_primary": event.invite_link.is_primary,
                },
            )
        )
        await db.execute(link_stmt)

    # 5. Determine the Inviter
    # Case A: Joined via invite link -> inviter is the creator of the invite link
    # Case B: Direct addition by an existing member -> inviter is the actor (from_user)
    # Case C: Organic / public join -> no inviter
    inviter_id: int | None = None
    if link_creator_id:
        inviter_id = link_creator_id
    elif actor_payload.id != joining_user_payload.id:
        inviter_id = actor_payload.id

    is_joining = old_status in LEAVE_STATUSES and new_status in JOIN_STATUSES
    is_leaving = old_status in JOIN_STATUSES and new_status in LEAVE_STATUSES

    # 6. Check existing membership record for idempotency
    existing_member_query = select(TelegramChatMember).where(
        TelegramChatMember.chat_id == chat_payload.id,
        TelegramChatMember.user_id == joining_user_payload.id,
    )
    res = await db.execute(existing_member_query)
    existing_member = res.scalar_one_or_none()

    incremented = False

    if is_joining:
        if existing_member is None:
            # First-time join: record membership and credit the inviter
            new_member = TelegramChatMember(
                chat_id=chat_payload.id,
                user_id=joining_user_payload.id,
                inviter_user_id=inviter_id,
                invite_link=invite_link_str,
                status=new_status,
                joined_at=event_timestamp,
            )
            db.add(new_member)

            if inviter_id:
                # Atomically increment inviter stat
                stat_stmt = (
                    insert(TelegramInviteStat)
                    .values(
                        chat_id=chat_payload.id,
                        user_id=inviter_id,
                        total_invites=1,
                    )
                    .on_conflict_do_update(
                        index_elements=[TelegramInviteStat.chat_id, TelegramInviteStat.user_id],
                        set_={
                            "total_invites": TelegramInviteStat.total_invites + 1,
                            "updated_at": func.now(),
                        },
                    )
                )
                await db.execute(stat_stmt)
                incremented = True

                # Increment link usage if joined via link
                if invite_link_str:
                    await db.execute(
                        update(TelegramInviteLink)
                        .where(TelegramInviteLink.invite_link == invite_link_str)
                        .values(usage_count=TelegramInviteLink.usage_count + 1)
                    )
        else:
            # Rejoining: update status and timestamp, but do NOT increment count again
            existing_member.status = new_status
            existing_member.updated_at = func.now()
            logger.info(
                "User %d rejoined chat %d. Updated status without duplicate counter increment.",
                joining_user_payload.id,
                chat_payload.id,
            )

    elif is_leaving:
        if existing_member:
            existing_member.status = new_status
            existing_member.updated_at = func.now()

    else:
        # Other status transition (e.g., promoted to administrator, restricted permissions)
        if existing_member:
            existing_member.status = new_status
            existing_member.updated_at = func.now()

    return {
        "chat_id": chat_payload.id,
        "user_id": joining_user_payload.id,
        "inviter_id": inviter_id,
        "is_joining": is_joining,
        "is_leaving": is_leaving,
        "incremented": incremented,
    }


async def process_telegram_webhook_update(
    db: AsyncSession,
    update_data: TelegramWebhookUpdate,
) -> dict[str, Any]:
    """Dispatches webhook update to appropriate handler."""
    if update_data.chat_member:
        return await process_chat_member_updated(db, update_data.chat_member)

    if update_data.my_chat_member:
        # Bot's own membership status changed (e.g., added/removed as admin)
        logger.info(
            "Bot status in chat %d changed from %s to %s",
            update_data.my_chat_member.chat.id,
            update_data.my_chat_member.old_chat_member.status,
            update_data.my_chat_member.new_chat_member.status,
        )
        # Update chat active state if bot was removed
        is_active = update_data.my_chat_member.new_chat_member.status in JOIN_STATUSES
        chat_stmt = (
            insert(TelegramChat)
            .values(
                chat_id=update_data.my_chat_member.chat.id,
                title=update_data.my_chat_member.chat.title,
                type=update_data.my_chat_member.chat.type,
                is_active=is_active,
            )
            .on_conflict_do_update(
                index_elements=[TelegramChat.chat_id],
                set_={"is_active": is_active, "updated_at": func.now()},
            )
        )
        await db.execute(chat_stmt)
        return {"handled": True, "type": "my_chat_member", "is_active": is_active}

    return {"handled": False, "type": "ignored"}


async def get_user_invite_stats(
    db: AsyncSession,
    chat_id: int,
    user_id: int,
) -> TelegramInviteStat | None:
    """Fetches total invite counter for a specific user in a chat."""
    query = select(TelegramInviteStat).where(
        TelegramInviteStat.chat_id == chat_id,
        TelegramInviteStat.user_id == user_id,
    )
    res = await db.execute(query)
    return res.scalar_one_or_none()


async def get_chat_leaderboard(
    db: AsyncSession,
    chat_id: int,
    limit: int = 20,
) -> list[TelegramLeaderboardEntry]:
    """Retrieves the top inviters in a specified chat."""
    query = (
        select(
            TelegramInviteStat.user_id,
            TelegramUser.username,
            TelegramUser.first_name,
            TelegramInviteStat.total_invites,
        )
        .join(TelegramUser, TelegramUser.user_id == TelegramInviteStat.user_id)
        .where(TelegramInviteStat.chat_id == chat_id)
        .order_by(TelegramInviteStat.total_invites.desc())
        .limit(limit)
    )
    res = await db.execute(query)
    rows = res.all()
    return [
        TelegramLeaderboardEntry(
            user_id=row.user_id,
            username=row.username,
            first_name=row.first_name,
            total_invites=row.total_invites,
        )
        for row in rows
    ]
