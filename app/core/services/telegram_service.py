import asyncio
import csv
from datetime import datetime, timezone
import io
import logging
from typing import Any

import httpx
from sqlalchemy import func, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.schemas.telegram import (
    CallbackQueryPayload,
    ChatMemberUpdatedPayload,
    TelegramChatOut,
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

    updates = allowed_updates or ["chat_member", "my_chat_member", "message", "callback_query"]

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


async def send_message(
    chat_id: int,
    text: str,
    parse_mode: str = "HTML",
    reply_markup: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    """Helper to send a message to a chat using Telegram Bot API."""
    token = settings.TELEGRAM_BOT_TOKEN
    if not token:
        return None
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload: dict[str, Any] = {"chat_id": chat_id, "text": text, "parse_mode": parse_mode}
    if reply_markup is not None:
        payload["reply_markup"] = reply_markup
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.post(url, json=payload)
            return resp.json()
    except Exception as exc:
        logger.warning("Failed to send Telegram message to chat %d: %s", chat_id, exc)
        return None


async def edit_message_text(
    chat_id: int,
    message_id: int,
    text: str,
    parse_mode: str = "HTML",
    reply_markup: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    """Edits an existing Telegram message in-place for seamless menu navigation."""
    token = settings.TELEGRAM_BOT_TOKEN
    if not token:
        return None
    url = f"https://api.telegram.org/bot{token}/editMessageText"
    payload: dict[str, Any] = {
        "chat_id": chat_id,
        "message_id": message_id,
        "text": text,
        "parse_mode": parse_mode,
    }
    if reply_markup is not None:
        payload["reply_markup"] = reply_markup
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.post(url, json=payload)
            return resp.json()
    except Exception as exc:
        logger.warning("Failed to edit Telegram message %d in chat %d: %s", message_id, chat_id, exc)
        return None


async def answer_callback_query(
    callback_query_id: str,
    text: str | None = None,
    show_alert: bool = False,
) -> None:
    """Acknowledges an inline button callback query to dismiss the Telegram loading indicator."""
    token = settings.TELEGRAM_BOT_TOKEN
    if not token:
        return
    url = f"https://api.telegram.org/bot{token}/answerCallbackQuery"
    payload: dict[str, Any] = {"callback_query_id": callback_query_id}
    if text:
        payload["text"] = text
        payload["show_alert"] = show_alert
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            await client.post(url, json=payload)
    except Exception as exc:
        logger.warning("Failed to answer callback query %s: %s", callback_query_id, exc)


async def send_document(
    chat_id: int,
    filename: str,
    content_bytes: bytes,
    caption: str | None = None,
) -> dict[str, Any] | None:
    """Sends a downloadable file (e.g. CSV report) directly to a Telegram chat."""
    token = settings.TELEGRAM_BOT_TOKEN
    if not token:
        return None
    url = f"https://api.telegram.org/bot{token}/sendDocument"
    files = {"document": (filename, content_bytes, "text/csv")}
    data = {"chat_id": str(chat_id)}
    if caption:
        data["caption"] = caption
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(url, data=data, files=files)
            return resp.json()
    except Exception as exc:
        logger.warning("Failed to send Telegram document to chat %d: %s", chat_id, exc)
        return None


async def is_chat_admin(chat_id: int, user_id: int) -> bool:
    """Verifies with Telegram Bot API whether a user is an administrator or creator in a chat."""
    token = settings.TELEGRAM_BOT_TOKEN
    if not token:
        return False
    url = f"https://api.telegram.org/bot{token}/getChatMember"
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(url, params={"chat_id": chat_id, "user_id": user_id})
            data = resp.json()
            if not data.get("ok"):
                return False
            status = data.get("result", {}).get("status")
            return status in ("creator", "administrator")
    except Exception as exc:
        logger.warning("Error verifying admin status for user %d in chat %d: %s", user_id, chat_id, exc)
        return False


async def get_admin_chats(db: AsyncSession, user_id: int) -> list[TelegramChat]:
    """Finds all tracked chats in which the user holds administrative permissions."""
    res = await db.execute(select(TelegramChat).where(TelegramChat.is_active == True))  # noqa: E712
    all_chats = res.scalars().all()
    if not all_chats:
        return []

    async def _check(c: TelegramChat) -> TelegramChat | None:
        if await is_chat_admin(chat_id=c.chat_id, user_id=user_id):
            return c
        return None

    results = await asyncio.gather(*[_check(c) for c in all_chats], return_exceptions=True)
    return [c for c in results if isinstance(c, TelegramChat)]


async def generate_chat_invites_csv(db: AsyncSession, chat_id: int) -> str:
    """Generates a CSV report of all inviters and their invite totals in a chat."""
    query = (
        select(
            TelegramInviteStat.user_id,
            TelegramUser.username,
            TelegramUser.first_name,
            TelegramUser.last_name,
            TelegramInviteStat.total_invites,
            TelegramInviteStat.updated_at,
        )
        .join(TelegramUser, TelegramUser.user_id == TelegramInviteStat.user_id)
        .where(TelegramInviteStat.chat_id == chat_id)
        .order_by(TelegramInviteStat.total_invites.desc())
    )
    res = await db.execute(query)
    rows = res.all()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "Rank",
        "Telegram User ID",
        "Username",
        "First Name",
        "Last Name",
        "Total Invites",
        "Last Invite Timestamp (UTC)",
    ])
    for rank, row in enumerate(rows, start=1):
        writer.writerow([
            rank,
            row.user_id,
            f"@{row.username}" if row.username else "",
            row.first_name,
            row.last_name or "",
            row.total_invites,
            row.updated_at.strftime("%Y-%m-%d %H:%M:%S") if row.updated_at else "",
        ])
    return output.getvalue()


def build_main_menu(admin_chats: list[TelegramChat], user_first_name: str = "Admin") -> tuple[str, dict[str, Any]]:
    """Builds the primary private-message admin menu with list of authorized groups."""
    text = (
        f"🛡️ <b>Zemen Bot — Admin Control Panel</b>\n\n"
        f"Welcome, {user_first_name}! You are recognized as an administrator in the following group(s):\n\n"
        f"Select a group below to view invite counts, leaderboards, or export data:"
    )
    keyboard = []
    for chat in admin_chats:
        title = chat.title or f"Chat {chat.chat_id}"
        keyboard.append([{"text": f"👥 {title}", "callback_data": f"chat:{chat.chat_id}"}])

    keyboard.append([
        {"text": "🔄 Refresh", "callback_data": "menu:main"},
        {"text": "ℹ️ About", "callback_data": "menu:about"},
    ])
    return text, {"inline_keyboard": keyboard}


async def build_chat_detail_menu(db: AsyncSession, chat_id: int) -> tuple[str, dict[str, Any]]:
    """Builds the detailed analytics view for a specific chat."""
    chat = await get_chat(db, chat_id=chat_id)
    if not chat:
        return "❌ Chat not found in database.", {
            "inline_keyboard": [[{"text": "« Back to Main Menu", "callback_data": "menu:main"}]]
        }

    status_icon = "Active ✅" if chat.is_active else "Inactive ❌"
    text = (
        f"📊 <b>Group Overview: {chat.title or 'Telegram Chat'}</b>\n\n"
        f"• <b>Chat ID:</b> <code>{chat.chat_id}</code>\n"
        f"• <b>Type:</b> <i>{chat.type}</i>\n"
        f"• <b>Tracked Members:</b> <b>{chat.total_members}</b>\n"
        f"• <b>Verified Invites:</b> <b>{chat.total_invites}</b>\n"
        f"• <b>Status:</b> {status_icon}\n\n"
        f"Select an action:"
    )
    keyboard = [
        [{"text": "🏆 Top Inviters (Leaderboard)", "callback_data": f"lb:{chat_id}"}],
        [{"text": "🔗 Invite Links Performance", "callback_data": f"links:{chat_id}"}],
        [{"text": "📥 Export Report (CSV)", "callback_data": f"export:{chat_id}"}],
        [{"text": "« Back to Groups", "callback_data": "menu:main"}],
    ]
    return text, {"inline_keyboard": keyboard}


async def build_leaderboard_menu(db: AsyncSession, chat_id: int) -> tuple[str, dict[str, Any]]:
    """Builds the top inviters leaderboard view for a specific chat."""
    leaderboard = await get_chat_leaderboard(db, chat_id=chat_id, limit=10)
    text_lines = [f"🏆 <b>Top Inviters Leaderboard</b>\n<code>Chat ID: {chat_id}</code>\n"]
    if not leaderboard:
        text_lines.append("<i>No verified invites recorded in this chat yet.</i>")
    else:
        medals = {1: "🥇", 2: "🥈", 3: "🥉"}
        for idx, entry in enumerate(leaderboard, start=1):
            icon = medals.get(idx, f"<b>{idx}.</b>")
            user_display = f"@{entry.username}" if entry.username else entry.first_name
            text_lines.append(f"{icon} {user_display} — <b>{entry.total_invites}</b> invites")

    keyboard = [
        [{"text": "📥 Export Full CSV", "callback_data": f"export:{chat_id}"}],
        [{"text": "« Back to Group", "callback_data": f"chat:{chat_id}"}],
        [{"text": "« Main Menu", "callback_data": "menu:main"}],
    ]
    return "\n".join(text_lines), {"inline_keyboard": keyboard}


async def build_links_menu(db: AsyncSession, chat_id: int) -> tuple[str, dict[str, Any]]:
    """Builds the invite links performance breakdown view."""
    query = (
        select(TelegramInviteLink)
        .where(TelegramInviteLink.chat_id == chat_id)
        .order_by(TelegramInviteLink.usage_count.desc())
        .limit(10)
    )
    res = await db.execute(query)
    links = res.scalars().all()

    text_lines = [f"🔗 <b>Invite Links Performance</b>\n<code>Chat ID: {chat_id}</code>\n"]
    if not links:
        text_lines.append("<i>No tracked invite links recorded yet for this chat.</i>")
    else:
        for idx, link in enumerate(links, start=1):
            name_label = f" ({link.name})" if link.name else ""
            primary_tag = " ⭐ Primary" if link.is_primary else ""
            text_lines.append(
                f"<b>{idx}.</b> <code>{link.invite_link}</code>{name_label}{primary_tag}\n"
                f"   ↳ <b>{link.usage_count}</b> verified joins"
            )

    keyboard = [
        [{"text": "« Back to Group", "callback_data": f"chat:{chat_id}"}],
        [{"text": "« Main Menu", "callback_data": "menu:main"}],
    ]
    return "\n".join(text_lines), {"inline_keyboard": keyboard}


async def handle_callback_query(
    db: AsyncSession,
    callback_query: CallbackQueryPayload,
) -> dict[str, Any]:
    """Handles button clicks from inline keyboards in private messages."""
    if not callback_query.message:
        await answer_callback_query(callback_query.id, "Session expired.")
        return {"handled": False}

    dm_chat_id = callback_query.message.chat.id
    message_id = callback_query.message.message_id
    user_id = callback_query.from_user.id
    data = callback_query.data or ""

    if data == "menu:main":
        admin_chats = await get_admin_chats(db, user_id=user_id)
        if not admin_chats:
            await edit_message_text(
                dm_chat_id,
                message_id,
                "⛔ <b>Access Restricted</b>\n\nYou are not recognized as an administrator in any tracked groups.",
            )
        else:
            text, markup = build_main_menu(admin_chats, user_first_name=callback_query.from_user.first_name)
            await edit_message_text(dm_chat_id, message_id, text, reply_markup=markup)
        await answer_callback_query(callback_query.id)
        return {"handled": True, "action": "menu_main"}

    if data == "menu:about":
        about_text = (
            "ℹ️ <b>About Zemen Invite Tracker</b>\n\n"
            "• Version: <code>1.0.0</code>\n"
            "• Automatically monitors group joins via direct adds and invite links.\n"
            "• Deduplicates rejoining members and calculates accurate invite statistics.\n"
            "• Accessible exclusively to verified group administrators."
        )
        markup = {"inline_keyboard": [[{"text": "« Back to Main Menu", "callback_data": "menu:main"}]]}
        await edit_message_text(dm_chat_id, message_id, about_text, reply_markup=markup)
        await answer_callback_query(callback_query.id)
        return {"handled": True, "action": "menu_about"}

    if data.startswith("chat:"):
        target_chat_id = int(data.split(":")[1])
        if not await is_chat_admin(target_chat_id, user_id):
            await answer_callback_query(callback_query.id, "⛔ You are not an admin of this group.", show_alert=True)
            return {"handled": False, "error": "unauthorized"}
        text, markup = await build_chat_detail_menu(db, target_chat_id)
        await edit_message_text(dm_chat_id, message_id, text, reply_markup=markup)
        await answer_callback_query(callback_query.id)
        return {"handled": True, "action": "chat_detail", "chat_id": target_chat_id}

    if data.startswith("lb:"):
        target_chat_id = int(data.split(":")[1])
        if not await is_chat_admin(target_chat_id, user_id):
            await answer_callback_query(callback_query.id, "⛔ You are not an admin of this group.", show_alert=True)
            return {"handled": False, "error": "unauthorized"}
        text, markup = await build_leaderboard_menu(db, target_chat_id)
        await edit_message_text(dm_chat_id, message_id, text, reply_markup=markup)
        await answer_callback_query(callback_query.id)
        return {"handled": True, "action": "leaderboard", "chat_id": target_chat_id}

    if data.startswith("links:"):
        target_chat_id = int(data.split(":")[1])
        if not await is_chat_admin(target_chat_id, user_id):
            await answer_callback_query(callback_query.id, "⛔ You are not an admin of this group.", show_alert=True)
            return {"handled": False, "error": "unauthorized"}
        text, markup = await build_links_menu(db, target_chat_id)
        await edit_message_text(dm_chat_id, message_id, text, reply_markup=markup)
        await answer_callback_query(callback_query.id)
        return {"handled": True, "action": "links", "chat_id": target_chat_id}

    if data.startswith("export:"):
        target_chat_id = int(data.split(":")[1])
        if not await is_chat_admin(target_chat_id, user_id):
            await answer_callback_query(callback_query.id, "⛔ You are not an admin of this group.", show_alert=True)
            return {"handled": False, "error": "unauthorized"}
        await answer_callback_query(callback_query.id, "Generating CSV report...")
        csv_data = await generate_chat_invites_csv(db, target_chat_id)
        filename = f"invites_{abs(target_chat_id)}_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}.csv"
        caption = f"📊 <b>Invite Report</b>\n• Chat ID: <code>{target_chat_id}</code>\n• Generated: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}"
        await send_document(dm_chat_id, filename, csv_data.encode("utf-8"), caption=caption)
        return {"handled": True, "action": "export", "chat_id": target_chat_id}

    await answer_callback_query(callback_query.id)
    return {"handled": False, "type": "unknown_callback"}


async def process_telegram_webhook_update(
    db: AsyncSession,
    update_data: TelegramWebhookUpdate,
) -> dict[str, Any]:
    """Dispatches webhook update to appropriate handler."""
    if update_data.chat_member:
        return await process_chat_member_updated(db, update_data.chat_member)

    if update_data.callback_query:
        return await handle_callback_query(db, update_data.callback_query)

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
                set_={
                    "title": update_data.my_chat_member.chat.title,
                    "type": update_data.my_chat_member.chat.type,
                    "is_active": is_active,
                    "updated_at": func.now(),
                },
            )
        )
        await db.execute(chat_stmt)
        return {"handled": True, "type": "my_chat_member", "is_active": is_active}

    if update_data.message:
        msg = update_data.message
        # Upsert Chat to record its chat_id and details
        chat_stmt = (
            insert(TelegramChat)
            .values(
                chat_id=msg.chat.id,
                title=msg.chat.title,
                type=msg.chat.type,
                is_active=True,
            )
            .on_conflict_do_update(
                index_elements=[TelegramChat.chat_id],
                set_={
                    "title": msg.chat.title,
                    "type": msg.chat.type,
                    "is_active": True,
                    "updated_at": func.now(),
                },
            )
        )
        await db.execute(chat_stmt)

        # Upsert sending user
        if msg.from_user:
            user_stmt = (
                insert(TelegramUser)
                .values(
                    user_id=msg.from_user.id,
                    username=msg.from_user.username,
                    first_name=msg.from_user.first_name,
                    last_name=msg.from_user.last_name,
                    is_bot=msg.from_user.is_bot,
                )
                .on_conflict_do_update(
                    index_elements=[TelegramUser.user_id],
                    set_={
                        "username": msg.from_user.username,
                        "first_name": msg.from_user.first_name,
                        "last_name": msg.from_user.last_name,
                        "is_bot": msg.from_user.is_bot,
                        "updated_at": func.now(),
                    },
                )
            )
            await db.execute(user_stmt)

        # 1. Private Messages (Direct Message with Bot) -> Admin Dashboard
        if msg.chat.type == "private" and msg.from_user:
            admin_chats = await get_admin_chats(db, user_id=msg.from_user.id)
            if not admin_chats:
                restricted_msg = (
                    f"⛔ <b>Access Restricted</b>\n\n"
                    f"Hi {msg.from_user.first_name}! This bot is configured for group administrators only.\n\n"
                    f"You are currently not recognized as an administrator in any of the tracked groups.\n\n"
                    f"<i>Note: Make sure the bot is added to your group as an Administrator with 'Invite Users via Link' permission.</i>"
                )
                await send_message(chat_id=msg.chat.id, text=restricted_msg)
            else:
                text, markup = build_main_menu(admin_chats, user_first_name=msg.from_user.first_name)
                await send_message(chat_id=msg.chat.id, text=text, reply_markup=markup)
            return {"handled": True, "type": "private_message", "is_admin": bool(admin_chats)}

        # 2. Group Messages -> Direct admins to DM to keep group chat clean
        raw_text = (msg.text or "").strip().lower()
        if raw_text in ("/admin", "/dashboard", "/stats", "/menu", "/start"):
            dm_notice = (
                f"🔒 <b>Admin Control Panel</b>\n\n"
                f"Hi {msg.from_user.first_name if msg.from_user else 'there'}! Administrative statistics, leaderboards, and reports are accessible exclusively in <b>Private Messages</b> to avoid group chat clutter.\n\n"
                f"👉 Please open a direct message with me to view your dashboard."
            )
            await send_message(chat_id=msg.chat.id, text=dm_notice)
        elif raw_text in ("/id", "/chatid", "/chat_id"):
            reply = (
                f"📋 <b>Telegram Chat Info</b>\n\n"
                f"• <b>Chat ID:</b> <code>{msg.chat.id}</code>\n"
                f"• <b>Title:</b> {msg.chat.title or 'Group'}\n"
                f"• <b>Type:</b> {msg.chat.type}"
            )
            await send_message(chat_id=msg.chat.id, text=reply)

        return {"handled": True, "type": "group_message", "chat_id": msg.chat.id}

    return {"handled": False, "type": "ignored"}


async def list_chats(
    db: AsyncSession,
    limit: int = 50,
    offset: int = 0,
) -> list[TelegramChatOut]:
    """Lists all tracked chats with current active members and total invite counts."""
    member_count_subq = (
        select(
            TelegramChatMember.chat_id,
            func.count(TelegramChatMember.id).label("total_members"),
        )
        .where(TelegramChatMember.status.in_(["member", "administrator"]))
        .group_by(TelegramChatMember.chat_id)
        .subquery()
    )

    invite_count_subq = (
        select(
            TelegramInviteStat.chat_id,
            func.coalesce(func.sum(TelegramInviteStat.total_invites), 0).label("total_invites"),
        )
        .group_by(TelegramInviteStat.chat_id)
        .subquery()
    )

    query = (
        select(
            TelegramChat,
            func.coalesce(member_count_subq.c.total_members, 0).label("total_members"),
            func.coalesce(invite_count_subq.c.total_invites, 0).label("total_invites"),
        )
        .outerjoin(member_count_subq, TelegramChat.chat_id == member_count_subq.c.chat_id)
        .outerjoin(invite_count_subq, TelegramChat.chat_id == invite_count_subq.c.chat_id)
        .order_by(TelegramChat.updated_at.desc())
        .limit(limit)
        .offset(offset)
    )
    res = await db.execute(query)
    rows = res.all()

    return [
        TelegramChatOut(
            chat_id=chat.chat_id,
            title=chat.title,
            type=chat.type,
            is_active=chat.is_active,
            total_members=total_members,
            total_invites=total_invites,
            created_at=chat.created_at,
            updated_at=chat.updated_at,
        )
        for chat, total_members, total_invites in rows
    ]


async def get_chat(
    db: AsyncSession,
    chat_id: int,
) -> TelegramChatOut | None:
    """Retrieves metadata and counters for a single chat."""
    member_count_subq = (
        select(
            TelegramChatMember.chat_id,
            func.count(TelegramChatMember.id).label("total_members"),
        )
        .where(TelegramChatMember.status.in_(["member", "administrator"]))
        .group_by(TelegramChatMember.chat_id)
        .subquery()
    )

    invite_count_subq = (
        select(
            TelegramInviteStat.chat_id,
            func.coalesce(func.sum(TelegramInviteStat.total_invites), 0).label("total_invites"),
        )
        .group_by(TelegramInviteStat.chat_id)
        .subquery()
    )

    query = (
        select(
            TelegramChat,
            func.coalesce(member_count_subq.c.total_members, 0).label("total_members"),
            func.coalesce(invite_count_subq.c.total_invites, 0).label("total_invites"),
        )
        .outerjoin(member_count_subq, TelegramChat.chat_id == member_count_subq.c.chat_id)
        .outerjoin(invite_count_subq, TelegramChat.chat_id == invite_count_subq.c.chat_id)
        .where(TelegramChat.chat_id == chat_id)
    )
    res = await db.execute(query)
    row = res.one_or_none()
    if not row:
        return None

    chat, total_members, total_invites = row
    return TelegramChatOut(
        chat_id=chat.chat_id,
        title=chat.title,
        type=chat.type,
        is_active=chat.is_active,
        total_members=total_members,
        total_invites=total_invites,
        created_at=chat.created_at,
        updated_at=chat.updated_at,
    )


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
