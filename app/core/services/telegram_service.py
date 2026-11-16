import asyncio
import csv
from datetime import datetime, timezone
import io
import logging
from typing import Any
import urllib.parse

import httpx
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
from app.persistence.repositories.telegram_repo import TelegramRepository
from app.persistence.sqlalchemy.models.telegram import (
    TelegramChat,
    TelegramInviteStat,
)

logger = logging.getLogger(__name__)

JOIN_STATUSES = {"member", "administrator", "restricted"}
LEAVE_STATUSES = {"left", "kicked"}


def _resolve_repo(db_or_repo: AsyncSession | TelegramRepository) -> TelegramRepository:
    """Helper to ensure a TelegramRepository instance is used."""
    if isinstance(db_or_repo, TelegramRepository):
        return db_or_repo
    return TelegramRepository(db_or_repo)


# =============================================================================
# Webhook Registration & Management
# =============================================================================

async def register_webhook(
    bot_token: str | None = None,
    webhook_url: str | None = None,
    secret_token: str | None = None,
    allowed_updates: list[str] | None = None,
) -> TelegramWebhookRegistrationResponse:
    """Registers the webhook with Telegram Bot API with allowed_updates."""
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
            description = data.get(
                "description", "Webhook registered successfully" if is_ok else "Registration failed"
            )
            if is_ok:
                logger.info(
                    "Telegram webhook registered successfully at %s with allowed_updates=%s",
                    target_url,
                    updates,
                )
                await set_bot_commands(token)
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


async def set_bot_commands(bot_token: str | None = None) -> bool:
    """Configures the official Telegram bot command menu via setMyCommands."""
    token = bot_token or settings.TELEGRAM_BOT_TOKEN
    if not token:
        return False
    commands = [
        {"command": "start", "description": "Open dashboard & get your invite link"},
        {"command": "invite", "description": "Get your personal invite link & stats"},
        {"command": "leaderboard", "description": "View top inviters leaderboard"},
        {"command": "stats", "description": "View your invite count and rank"},
        {"command": "admin", "description": "Admin control panel (admins only)"},
        {"command": "help", "description": "Help guide and instructions"},
    ]
    url = f"https://api.telegram.org/bot{token}/setMyCommands"
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(url, json={"commands": commands})
            data = resp.json()
            return bool(data.get("ok", False))
    except Exception as exc:
        logger.warning("Failed to configure Telegram bot commands: %s", exc)
        return False


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


# =============================================================================
# Chat Member Updates & Invite Attribution
# =============================================================================

async def process_chat_member_updated(
    db: AsyncSession | TelegramRepository,
    event: ChatMemberUpdatedPayload,
) -> dict[str, Any]:
    """
    Parses a ChatMemberUpdated payload, records the event via TelegramRepository,
    and updates invite counts.
    Handles both direct additions (user added another) and invite link clicks.
    Guarantees idempotency to prevent duplicate increments on rejoins.
    """
    repo = _resolve_repo(db)
    chat_payload = event.chat
    joining_user_payload = event.new_chat_member.user
    actor_payload = event.from_user
    old_status = event.old_chat_member.status
    new_status = event.new_chat_member.status
    event_timestamp = datetime.fromtimestamp(event.date, tz=timezone.utc)

    # 1. Upsert Telegram Chat (only for group, supergroup, or channel)
    if chat_payload.type in ("group", "supergroup", "channel"):
        await repo.upsert_chat(
            chat_id=chat_payload.id,
            title=chat_payload.title,
            type=chat_payload.type,
            is_active=True,
        )

    # 2. Upsert Joining User
    await repo.upsert_user(
        user_id=joining_user_payload.id,
        username=joining_user_payload.username,
        first_name=joining_user_payload.first_name,
        last_name=joining_user_payload.last_name,
        is_bot=joining_user_payload.is_bot,
    )

    # 3. Upsert Actor User (if different from joining user)
    if actor_payload.id != joining_user_payload.id:
        await repo.upsert_user(
            user_id=actor_payload.id,
            username=actor_payload.username,
            first_name=actor_payload.first_name,
            last_name=actor_payload.last_name,
            is_bot=actor_payload.is_bot,
        )

    # 4. Upsert Link Creator User & Invite Link (if present)
    invite_link_str: str | None = None
    link_creator_id: int | None = None

    if event.invite_link:
        invite_link_str = event.invite_link.invite_link

        # Check if the invite link is registered in our database to a specific member
        db_link = await repo.get_invite_link(invite_link_str)
        if db_link and db_link.creator_user_id:
            # Attributed to the member who requested the unique link via the bot
            link_creator_id = db_link.creator_user_id
        elif event.invite_link.creator and not event.invite_link.creator.is_bot:
            link_creator_id = event.invite_link.creator.id
            await repo.upsert_user(
                user_id=event.invite_link.creator.id,
                username=event.invite_link.creator.username,
                first_name=event.invite_link.creator.first_name,
                last_name=event.invite_link.creator.last_name,
                is_bot=event.invite_link.creator.is_bot,
            )

        effective_creator_id = link_creator_id or (db_link.creator_user_id if db_link else None)
        effective_name = event.invite_link.name or (db_link.name if db_link else None)

        await repo.upsert_invite_link(
            invite_link=invite_link_str,
            chat_id=chat_payload.id,
            creator_user_id=effective_creator_id,
            name=effective_name,
            is_primary=event.invite_link.is_primary,
        )

    # 5. Determine the Inviter
    # Case A: Joined via invite link -> inviter is the creator of the invite link
    # Case B: Direct addition by an existing member -> inviter is the actor (from_user)
    # Case C: Organic / public join -> no inviter
    inviter_id: int | None = None
    if link_creator_id:
        inviter_id = link_creator_id
    elif actor_payload.id != joining_user_payload.id:
        inviter_id = actor_payload.id

    # The user must actually join the group (transition from left/kicked to member/admin/restricted)
    is_joining = old_status in LEAVE_STATUSES and new_status in JOIN_STATUSES
    is_leaving = old_status in JOIN_STATUSES and new_status in LEAVE_STATUSES

    # 6. Check existing membership record for idempotency
    existing_member = await repo.get_chat_member(
        chat_id=chat_payload.id,
        user_id=joining_user_payload.id,
    )

    incremented = False

    if is_joining:
        if existing_member is None:
            # First-time join: record membership and credit the inviter
            await repo.record_member_join(
                chat_id=chat_payload.id,
                user_id=joining_user_payload.id,
                inviter_user_id=inviter_id,
                invite_link=invite_link_str,
                status=new_status,
                joined_at=event_timestamp,
            )

            # Credit inviter only if present and the joining user is not a bot
            if inviter_id and not joining_user_payload.is_bot:
                await repo.increment_user_invites(
                    chat_id=chat_payload.id,
                    user_id=inviter_id,
                )
                incremented = True

                # Increment link usage if joined via link
                if invite_link_str:
                    await repo.increment_link_usage(invite_link=invite_link_str)
        else:
            # Rejoining: update status and timestamp, but do NOT increment count again
            existing_member.status = new_status
            await repo.update_member_status(
                chat_id=chat_payload.id,
                user_id=joining_user_payload.id,
                status=new_status,
            )
            logger.info(
                "User %d rejoined chat %d. Updated status without duplicate counter increment.",
                joining_user_payload.id,
                chat_payload.id,
            )

    elif is_leaving:
        if existing_member:
            existing_member.status = new_status
            await repo.update_member_status(
                chat_id=chat_payload.id,
                user_id=joining_user_payload.id,
                status=new_status,
            )

    else:
        # Other status transition (e.g. promoted to administrator, restricted permissions)
        if existing_member:
            existing_member.status = new_status
            await repo.update_member_status(
                chat_id=chat_payload.id,
                user_id=joining_user_payload.id,
                status=new_status,
            )

    return {
        "chat_id": chat_payload.id,
        "user_id": joining_user_payload.id,
        "inviter_id": inviter_id,
        "is_joining": is_joining,
        "is_leaving": is_leaving,
        "incremented": incremented,
    }


# =============================================================================
# Telegram Bot API Client Helpers
# =============================================================================

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


async def fetch_chat_info(chat_id: int) -> dict[str, Any] | None:
    """Fetches chat information directly from Telegram Bot API via getChat."""
    token = settings.TELEGRAM_BOT_TOKEN
    if not token:
        return None
    url = f"https://api.telegram.org/bot{token}/getChat"
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(url, params={"chat_id": chat_id})
            data = resp.json()
            if data.get("ok"):
                return data.get("result")
            return None
    except Exception as exc:
        logger.warning("Failed to fetch chat info for %d: %s", chat_id, exc)
        return None


_bot_username_cache: str | None = None


async def get_bot_username() -> str:
    """Retrieves and caches the bot username from Telegram Bot API."""
    global _bot_username_cache
    if _bot_username_cache:
        return _bot_username_cache
    token = settings.TELEGRAM_BOT_TOKEN
    if not token:
        return "zemen_service_bot"
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(f"https://api.telegram.org/bot{token}/getMe")
            data = resp.json()
            if data.get("ok"):
                username = data.get("result", {}).get("username")
                if username:
                    _bot_username_cache = username
                    return username
    except Exception as exc:
        logger.warning("Failed to fetch bot username: %s", exc)
    return "zemen_service_bot"


async def get_chat_member_status(chat_id: int, user_id: int) -> str | None:
    """Fetches membership status of a user in a chat via getChatMember."""
    token = settings.TELEGRAM_BOT_TOKEN
    if not token:
        return None
    url = f"https://api.telegram.org/bot{token}/getChatMember"
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(url, params={"chat_id": chat_id, "user_id": user_id})
            data = resp.json()
            if not data.get("ok"):
                return None
            return data.get("result", {}).get("status")
    except Exception as exc:
        logger.warning("Error fetching chat member status for user %d in chat %d: %s", user_id, chat_id, exc)
        return None


async def is_chat_member_or_admin(
    db: AsyncSession | TelegramRepository,
    chat_id: int,
    user_id: int,
) -> bool:
    """Verifies whether a user is an active member, creator, or administrator in a chat."""
    repo = _resolve_repo(db)
    # Check DB membership first
    existing = await repo.get_chat_member(chat_id=chat_id, user_id=user_id)
    if existing and existing.status in JOIN_STATUSES:
        return True

    # Fallback to Telegram Bot API
    status = await get_chat_member_status(chat_id=chat_id, user_id=user_id)
    if status in ("creator", "administrator", "member", "restricted"):
        # Record membership in DB so future checks are local
        if not existing:
            await repo.record_member_join(
                chat_id=chat_id,
                user_id=user_id,
                inviter_user_id=None,
                invite_link=None,
                status=status,
            )
        else:
            await repo.update_member_status(chat_id=chat_id, user_id=user_id, status=status)
        return True
    return False


async def create_chat_invite_link(
    chat_id: int,
    name: str | None = None,
) -> str | None:
    """Creates a new unique, trackable invite link for a chat via Telegram Bot API."""
    token = settings.TELEGRAM_BOT_TOKEN
    if not token:
        return None
    url = f"https://api.telegram.org/bot{token}/createChatInviteLink"
    payload: dict[str, Any] = {"chat_id": chat_id}
    if name:
        payload["name"] = name[:32]  # Telegram Bot API max name length is 32 chars
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(url, json=payload)
            data = resp.json()
            if data.get("ok"):
                return data["result"]["invite_link"]
            logger.warning("Telegram createChatInviteLink failed for chat %d: %s", chat_id, data)
            return None
    except Exception as exc:
        logger.warning("Exception calling createChatInviteLink for chat %d: %s", chat_id, exc)
        return None


async def get_or_create_user_invite_link(
    repo: TelegramRepository,
    chat_id: int,
    user_id: int,
    user_first_name: str,
) -> str | None:
    """Retrieves an existing personal invite link for the user or generates a new one."""
    existing = await repo.get_user_invite_link(chat_id=chat_id, user_id=user_id)
    if existing:
        return existing.invite_link

    link_name = f"{user_first_name[:15]} ({user_id})"
    new_link = await create_chat_invite_link(chat_id=chat_id, name=link_name)
    if new_link:
        await repo.upsert_invite_link(
            invite_link=new_link,
            chat_id=chat_id,
            creator_user_id=user_id,
            name=link_name,
            is_primary=False,
        )
        return new_link
    return None


async def get_admin_chats(
    db: AsyncSession | TelegramRepository,
    user_id: int,
) -> list[TelegramChat]:
    """Finds all tracked chats in which the user holds administrative permissions."""
    repo = _resolve_repo(db)
    all_chats = await repo.get_active_group_chats()
    if not all_chats:
        return []

    async def _check(c: TelegramChat) -> TelegramChat | None:
        if await is_chat_admin(chat_id=c.chat_id, user_id=user_id):
            return c
        return None

    results = await asyncio.gather(*[_check(c) for c in all_chats], return_exceptions=True)
    return [c for c in results if isinstance(c, TelegramChat)]


async def generate_chat_invites_csv(
    db: AsyncSession | TelegramRepository,
    chat_id: int,
) -> str:
    """Generates a CSV report of all inviters and their invite totals in a chat."""
    repo = _resolve_repo(db)
    rows = await repo.get_chat_invites_for_csv(chat_id)

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


# =============================================================================
# In-Bot Interactive Menu Builders
# =============================================================================

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

    if admin_chats:
        primary_chat = admin_chats[0]
        keyboard.append([{"text": "🔗 My Personal Invite Link", "callback_data": f"user_link:{primary_chat.chat_id}"}])

    keyboard.append([
        {"text": "🔄 Refresh", "callback_data": "menu:main"},
        {"text": "ℹ️ About", "callback_data": "menu:about"},
    ])
    return text, {"inline_keyboard": keyboard}


def build_user_invite_card(
    chat_title: str,
    chat_id: int,
    invite_link: str,
    total_invites: int,
    rank: int | None,
    is_admin: bool = False,
) -> tuple[str, dict[str, Any]]:
    """Builds the personal invite link and stats dashboard card for members."""
    rank_display = f"#{rank}" if rank else "Unranked"
    text = (
        f"🔗 <b>Your Personal Invite Link</b>\n"
        f"Group: <b>{chat_title}</b>\n\n"
        f"Share your unique link with friends and contacts. Anyone who joins using this link will be credited to your score!\n\n"
        f"👉 <code>{invite_link}</code>\n"
        f"<i>(Tap the link above to copy)</i>\n\n"
        f"📊 <b>Your Invite Stats:</b>\n"
        f"• Verified Invites: <b>{total_invites}</b>\n"
        f"• Current Rank: <b>{rank_display}</b>"
    )

    share_text = f"Join {chat_title} on Telegram:"
    share_url = f"https://t.me/share/url?url={urllib.parse.quote(invite_link)}&text={urllib.parse.quote(share_text)}"

    keyboard = [
        [{"text": "🔗 Share Invite Link", "url": share_url}],
        [
            {"text": "🏆 Leaderboard", "callback_data": f"user_lb:{chat_id}"},
            {"text": "🔄 Refresh Stats", "callback_data": f"user_stats:{chat_id}"},
        ],
    ]
    if is_admin:
        keyboard.append([{"text": "🛡️ Admin Panel", "callback_data": "menu:main"}])

    return text, {"inline_keyboard": keyboard}


async def build_user_leaderboard_view(
    db: AsyncSession | TelegramRepository,
    chat_id: int,
    user_id: int,
) -> tuple[str, dict[str, Any]]:
    """Builds the top inviters leaderboard view for regular members."""
    repo = _resolve_repo(db)
    chat = await repo.get_chat(chat_id)
    chat_title = chat.title if chat and chat.title else f"Group {chat_id}"
    leaderboard = await get_chat_leaderboard(repo, chat_id=chat_id, limit=10)
    user_stat = await repo.get_user_invite_stat(chat_id, user_id)
    user_rank = await repo.get_user_rank(chat_id, user_id)
    my_invites = user_stat.total_invites if user_stat else 0
    my_rank_str = f"#{user_rank}" if user_rank else "Unranked"

    text_lines = [
        f"🏆 <b>Top Inviters Leaderboard</b>",
        f"Group: <b>{chat_title}</b>\n",
    ]
    if not leaderboard:
        text_lines.append("<i>No verified invites recorded in this chat yet.</i>\n")
    else:
        medals = {1: "🥇", 2: "🥈", 3: "🥉"}
        for idx, entry in enumerate(leaderboard, start=1):
            icon = medals.get(idx, f"<b>{idx}.</b>")
            user_display = f"@{entry.username}" if entry.username else entry.first_name
            text_lines.append(f"{icon} {user_display} — <b>{entry.total_invites}</b> invites")
        text_lines.append("")

    text_lines.append(f"👤 <b>Your Standing:</b> <b>{my_invites}</b> invites (Rank: <b>{my_rank_str}</b>)")

    keyboard = [
        [{"text": "« Back to My Link", "callback_data": f"user_link:{chat_id}"}],
        [{"text": "🔄 Refresh", "callback_data": f"user_lb:{chat_id}"}],
    ]
    return "\n".join(text_lines), {"inline_keyboard": keyboard}


async def build_chat_detail_menu(
    db: AsyncSession | TelegramRepository,
    chat_id: int,
) -> tuple[str, dict[str, Any]]:
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
        [{"text": "🔗 My Personal Invite Link", "callback_data": f"user_link:{chat_id}"}],
        [{"text": "🏆 Top Inviters (Leaderboard)", "callback_data": f"lb:{chat_id}"}],
        [{"text": "🔗 Invite Links Performance", "callback_data": f"links:{chat_id}"}],
        [{"text": "📥 Export Report (CSV)", "callback_data": f"export:{chat_id}"}],
        [{"text": "« Back to Groups", "callback_data": "menu:main"}],
    ]
    return text, {"inline_keyboard": keyboard}


async def build_leaderboard_menu(
    db: AsyncSession | TelegramRepository,
    chat_id: int,
) -> tuple[str, dict[str, Any]]:
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


async def build_links_menu(
    db: AsyncSession | TelegramRepository,
    chat_id: int,
) -> tuple[str, dict[str, Any]]:
    """Builds the invite links performance breakdown view."""
    repo = _resolve_repo(db)
    links = await repo.list_top_invite_links(chat_id=chat_id, limit=10)

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


# =============================================================================
# Callback Query & Webhook Event Dispatcher
# =============================================================================

async def handle_callback_query(
    db: AsyncSession | TelegramRepository,
    callback_query: CallbackQueryPayload,
) -> dict[str, Any]:
    """Handles button clicks from inline keyboards in private messages."""
    repo = _resolve_repo(db)
    if not callback_query.message:
        await answer_callback_query(callback_query.id, "Session expired.")
        return {"handled": False}

    dm_chat_id = callback_query.message.chat.id
    message_id = callback_query.message.message_id
    user_id = callback_query.from_user.id
    data = callback_query.data or ""

    if data == "menu:main":
        admin_chats = await get_admin_chats(repo, user_id=user_id)
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
        text, markup = await build_chat_detail_menu(repo, target_chat_id)
        await edit_message_text(dm_chat_id, message_id, text, reply_markup=markup)
        await answer_callback_query(callback_query.id)
        return {"handled": True, "action": "chat_detail", "chat_id": target_chat_id}

    if data.startswith("lb:"):
        target_chat_id = int(data.split(":")[1])
        if not await is_chat_admin(target_chat_id, user_id):
            await answer_callback_query(callback_query.id, "⛔ You are not an admin of this group.", show_alert=True)
            return {"handled": False, "error": "unauthorized"}
        text, markup = await build_leaderboard_menu(repo, target_chat_id)
        await edit_message_text(dm_chat_id, message_id, text, reply_markup=markup)
        await answer_callback_query(callback_query.id)
        return {"handled": True, "action": "leaderboard", "chat_id": target_chat_id}

    if data.startswith("links:"):
        target_chat_id = int(data.split(":")[1])
        if not await is_chat_admin(target_chat_id, user_id):
            await answer_callback_query(callback_query.id, "⛔ You are not an admin of this group.", show_alert=True)
            return {"handled": False, "error": "unauthorized"}
        text, markup = await build_links_menu(repo, target_chat_id)
        await edit_message_text(dm_chat_id, message_id, text, reply_markup=markup)
        await answer_callback_query(callback_query.id)
        return {"handled": True, "action": "links", "chat_id": target_chat_id}

    if data.startswith("export:"):
        target_chat_id = int(data.split(":")[1])
        if not await is_chat_admin(target_chat_id, user_id):
            await answer_callback_query(callback_query.id, "⛔ You are not an admin of this group.", show_alert=True)
            return {"handled": False, "error": "unauthorized"}
        await answer_callback_query(callback_query.id, "Generating CSV report...")
        csv_data = await generate_chat_invites_csv(repo, target_chat_id)
        filename = f"invites_{abs(target_chat_id)}_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}.csv"
        caption = f"📊 <b>Invite Report</b>\n• Chat ID: <code>{target_chat_id}</code>\n• Generated: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}"
        await send_document(dm_chat_id, filename, csv_data.encode("utf-8"), caption=caption)
        return {"handled": True, "action": "export", "chat_id": target_chat_id}

    if data.startswith("user_link:") or data.startswith("user_stats:"):
        is_refresh = data.startswith("user_stats:")
        target_chat_id = int(data.split(":")[1])
        if not await is_chat_member_or_admin(repo, target_chat_id, user_id):
            await answer_callback_query(
                callback_query.id,
                "⛔ You are not recognized as an active member of this group. Please join the group first!",
                show_alert=True,
            )
            return {"handled": False, "error": "not_member"}

        chat = await repo.get_chat(target_chat_id)
        chat_title = chat.title if chat and chat.title else f"Group {target_chat_id}"
        invite_link = await get_or_create_user_invite_link(
            repo, target_chat_id, user_id, callback_query.from_user.first_name
        )
        if not invite_link:
            await answer_callback_query(
                callback_query.id,
                "❌ Unable to generate invite link. Ensure bot has admin permissions with 'Invite Users via Link'.",
                show_alert=True,
            )
            return {"handled": False, "error": "link_creation_failed"}

        stat = await repo.get_user_invite_stat(target_chat_id, user_id)
        rank = await repo.get_user_rank(target_chat_id, user_id)
        is_admin = await is_chat_admin(target_chat_id, user_id)
        text, markup = build_user_invite_card(
            chat_title=chat_title,
            chat_id=target_chat_id,
            invite_link=invite_link,
            total_invites=stat.total_invites if stat else 0,
            rank=rank,
            is_admin=is_admin,
        )
        await edit_message_text(dm_chat_id, message_id, text, reply_markup=markup)
        if is_refresh:
            await answer_callback_query(callback_query.id, "Stats refreshed! 🔄")
        else:
            await answer_callback_query(callback_query.id)
        return {"handled": True, "action": "user_link", "chat_id": target_chat_id}

    if data.startswith("user_lb:"):
        target_chat_id = int(data.split(":")[1])
        text, markup = await build_user_leaderboard_view(repo, target_chat_id, user_id)
        await edit_message_text(dm_chat_id, message_id, text, reply_markup=markup)
        await answer_callback_query(callback_query.id)
        return {"handled": True, "action": "user_leaderboard", "chat_id": target_chat_id}

    await answer_callback_query(callback_query.id)
    return {"handled": False, "type": "unknown_callback"}


async def process_telegram_webhook_update(
    db: AsyncSession | TelegramRepository,
    update_data: TelegramWebhookUpdate,
) -> dict[str, Any]:
    """Dispatches webhook update to appropriate handler using TelegramRepository."""
    repo = _resolve_repo(db)

    if update_data.chat_member:
        return await process_chat_member_updated(repo, update_data.chat_member)

    if update_data.callback_query:
        return await handle_callback_query(repo, update_data.callback_query)

    if update_data.my_chat_member:
        # Bot's own membership status changed (e.g. added/removed as admin)
        logger.info(
            "Bot status in chat %d changed from %s to %s",
            update_data.my_chat_member.chat.id,
            update_data.my_chat_member.old_chat_member.status,
            update_data.my_chat_member.new_chat_member.status,
        )
        if update_data.my_chat_member.chat.type in ("group", "supergroup", "channel"):
            is_active = update_data.my_chat_member.new_chat_member.status in JOIN_STATUSES
            await repo.upsert_chat(
                chat_id=update_data.my_chat_member.chat.id,
                title=update_data.my_chat_member.chat.title,
                type=update_data.my_chat_member.chat.type,
                is_active=is_active,
            )
            return {"handled": True, "type": "my_chat_member", "is_active": is_active}
        return {"handled": True, "type": "my_chat_member"}

    if update_data.message:
        msg = update_data.message
        # Upsert Chat to record its chat_id and details (only for groups, supergroups, and channels)
        if msg.chat.type in ("group", "supergroup", "channel"):
            await repo.upsert_chat(
                chat_id=msg.chat.id,
                title=msg.chat.title,
                type=msg.chat.type,
                is_active=True,
            )

        # Upsert sending user
        if msg.from_user:
            await repo.upsert_user(
                user_id=msg.from_user.id,
                username=msg.from_user.username,
                first_name=msg.from_user.first_name,
                last_name=msg.from_user.last_name,
                is_bot=msg.from_user.is_bot,
            )

        # 1. Private Messages (Direct Message with Bot) -> Admin Dashboard & Member Invite Links
        if msg.chat.type == "private" and msg.from_user:
            raw_text = (msg.text or "").strip()
            parts = raw_text.split()
            first_word = parts[0].lower() if parts else ""
            command = first_word.split("@")[0]

            # Support registering a chat manually: /register <chat_id> or sending the chat ID directly
            if command in ("/register", "/addgroup", "/track") or (
                raw_text.lstrip("-").isdigit() and (raw_text.startswith("-100") or raw_text.startswith("-"))
            ):
                target_chat_str = ""
                if len(parts) > 1:
                    target_chat_str = parts[1]
                elif raw_text.lstrip("-").isdigit():
                    target_chat_str = raw_text

                if target_chat_str:
                    try:
                        target_chat_id = int(target_chat_str)
                    except ValueError:
                        await send_message(
                            chat_id=msg.chat.id,
                            text="⚠️ <b>Invalid Chat ID format</b>. Chat IDs are usually negative numbers like <code>-1002839533734</code>.",
                        )
                        return {"handled": True, "type": "private_message", "action": "register_invalid"}

                    chat_info = await fetch_chat_info(target_chat_id)
                    if not chat_info:
                        await send_message(
                            chat_id=msg.chat.id,
                            text=(
                                f"❌ <b>Unable to find group <code>{target_chat_id}</code></b>\n\n"
                                f"Please make sure the bot is added to your group as an <b>Administrator</b> with 'Invite Users via Link' permission."
                            ),
                        )
                        return {"handled": True, "type": "private_message", "action": "register_not_found"}

                    chat_type = chat_info.get("type", "group")
                    if chat_type not in ("group", "supergroup", "channel"):
                        await send_message(
                            chat_id=msg.chat.id,
                            text="⚠️ Only groups, supergroups, and channels can be tracked.",
                        )
                        return {"handled": True, "type": "private_message", "action": "register_invalid_type"}

                    # Verify admin permission
                    if not await is_chat_admin(chat_id=target_chat_id, user_id=msg.from_user.id):
                        await send_message(
                            chat_id=msg.chat.id,
                            text=f"⛔ <b>Permission Denied</b>\n\nYou are not an administrator of <b>{chat_info.get('title', target_chat_id)}</b>.",
                        )
                        return {"handled": True, "type": "private_message", "action": "register_unauthorized"}

                    # Upsert chat via repository
                    await repo.upsert_chat(
                        chat_id=target_chat_id,
                        title=chat_info.get("title"),
                        type=chat_type,
                        is_active=True,
                    )

                    admin_chats = await get_admin_chats(repo, user_id=msg.from_user.id)
                    menu_text, markup = build_main_menu(admin_chats, user_first_name=msg.from_user.first_name)
                    success_text = (
                        f"✅ <b>Group Connected Successfully!</b>\n\n"
                        f"<b>Group:</b> {chat_info.get('title')}\n"
                        f"<b>Chat ID:</b> <code>{target_chat_id}</code>\n\n"
                        f"{menu_text}"
                    )
                    await send_message(chat_id=msg.chat.id, text=success_text, reply_markup=markup)
                    return {"handled": True, "type": "private_message", "action": "registered_group"}

            # Deep linking support: /start invite_<chat_id> or /start link_<chat_id>
            deep_chat_id: int | None = None
            if command == "/start" and len(parts) > 1:
                arg = parts[1]
                for prefix in ("invite_", "link_", "ref_"):
                    if arg.startswith(prefix):
                        clean_arg = arg[len(prefix):]
                        try:
                            parsed_val = int(clean_arg)
                            if parsed_val > 0:
                                parsed_val = -parsed_val if str(parsed_val).startswith("100") else -int(f"100{parsed_val}")
                            deep_chat_id = parsed_val
                        except ValueError:
                            pass
                        break

            if deep_chat_id:
                chat = await repo.get_chat(deep_chat_id)
                if not chat:
                    for c in await repo.get_active_group_chats():
                        if abs(c.chat_id) == abs(deep_chat_id):
                            chat = c
                            deep_chat_id = c.chat_id
                            break

                if chat and await is_chat_member_or_admin(repo, deep_chat_id, msg.from_user.id):
                    invite_link = await get_or_create_user_invite_link(
                        repo, deep_chat_id, msg.from_user.id, msg.from_user.first_name
                    )
                    if invite_link:
                        stat = await repo.get_user_invite_stat(deep_chat_id, msg.from_user.id)
                        rank = await repo.get_user_rank(deep_chat_id, msg.from_user.id)
                        is_admin = await is_chat_admin(deep_chat_id, msg.from_user.id)
                        text, markup = build_user_invite_card(
                            chat_title=chat.title or f"Group {deep_chat_id}",
                            chat_id=deep_chat_id,
                            invite_link=invite_link,
                            total_invites=stat.total_invites if stat else 0,
                            rank=rank,
                            is_admin=is_admin,
                        )
                        await send_message(chat_id=msg.chat.id, text=text, reply_markup=markup)
                        return {"handled": True, "type": "private_message", "action": "deep_link_invite"}

                if chat:
                    chat_info = await fetch_chat_info(deep_chat_id)
                    group_title = chat.title or (chat_info.get("title") if chat_info else "the group")
                    join_url = (chat_info.get("invite_link") if chat_info else None) or (
                        f"https://t.me/{chat_info.get('username')}" if chat_info and chat_info.get("username") else None
                    )
                    welcome_msg = (
                        f"👋 <b>Welcome, {msg.from_user.first_name}!</b>\n\n"
                        f"To get your personal invite link and track your invites for <b>{group_title}</b>, please join the group first:"
                    )
                    buttons = []
                    if join_url:
                        buttons.append([{"text": f"👉 Join {group_title}", "url": join_url}])
                    buttons.append([{"text": "✅ I've Joined! Get My Link", "callback_data": f"user_link:{deep_chat_id}"}])
                    await send_message(chat_id=msg.chat.id, text=welcome_msg, reply_markup={"inline_keyboard": buttons})
                    return {"handled": True, "type": "private_message", "action": "deep_link_not_joined"}

            # Direct member commands: /invite, /link, /myref, /mystats, /stats
            is_invite_cmd = command in ("/invite", "/link", "/myref", "/mystats", "/stats")
            admin_chats = await get_admin_chats(repo, user_id=msg.from_user.id)

            if is_invite_cmd:
                target_chat: TelegramChat | None = None
                if admin_chats:
                    target_chat = admin_chats[0]
                else:
                    active_chats = await repo.get_active_group_chats()
                    member_chats = [c for c in active_chats if await is_chat_member_or_admin(repo, c.chat_id, msg.from_user.id)]
                    target_chat = member_chats[0] if member_chats else (active_chats[0] if active_chats else None)

                if target_chat and await is_chat_member_or_admin(repo, target_chat.chat_id, msg.from_user.id):
                    invite_link = await get_or_create_user_invite_link(
                        repo, target_chat.chat_id, msg.from_user.id, msg.from_user.first_name
                    )
                    if invite_link:
                        stat = await repo.get_user_invite_stat(target_chat.chat_id, msg.from_user.id)
                        rank = await repo.get_user_rank(target_chat.chat_id, msg.from_user.id)
                        is_admin = bool(admin_chats)
                        text, markup = build_user_invite_card(
                            chat_title=target_chat.title or "Group",
                            chat_id=target_chat.chat_id,
                            invite_link=invite_link,
                            total_invites=stat.total_invites if stat else 0,
                            rank=rank,
                            is_admin=is_admin,
                        )
                        await send_message(chat_id=msg.chat.id, text=text, reply_markup=markup)
                        return {"handled": True, "type": "private_message", "action": "user_invite_card"}

            # Leaderboard command: /leaderboard, /top, /lb
            if command in ("/leaderboard", "/top", "/lb"):
                target_chat = None
                if admin_chats:
                    target_chat = admin_chats[0]
                else:
                    active_chats = await repo.get_active_group_chats()
                    member_chats = [c for c in active_chats if await is_chat_member_or_admin(repo, c.chat_id, msg.from_user.id)]
                    target_chat = member_chats[0] if member_chats else (active_chats[0] if active_chats else None)

                if target_chat:
                    text, markup = await build_user_leaderboard_view(repo, target_chat.chat_id, msg.from_user.id)
                    await send_message(chat_id=msg.chat.id, text=text, reply_markup=markup)
                    return {"handled": True, "type": "private_message", "action": "user_leaderboard"}

            # Help & instructions command: /help, /info
            if command in ("/help", "/info"):
                help_text = (
                    "ℹ️ <b>Zemen Invite Tracker — Commands & Guide</b>\n\n"
                    "• <b>/invite</b> or <b>/link</b> — Get your personal trackable invite link and view stats\n"
                    "• <b>/leaderboard</b> — View top inviters in the group\n"
                    "• <b>/stats</b> — View your verified invite count and rank\n"
                    "• <b>/admin</b> — Open the Admin Control Panel (admins only)\n"
                    "• <b>/help</b> — Show this guide\n\n"
                    "<b>How invite tracking works:</b>\n"
                    "1. Share your unique link with friends or add members directly to the group.\n"
                    "2. When a member joins the group, your verified invite count increases by <b>+1</b>!\n"
                    "3. Duplicate rejoins and bots are automatically excluded."
                )
                await send_message(chat_id=msg.chat.id, text=help_text)
                return {"handled": True, "type": "private_message", "action": "help"}

            # Admin panel command: /admin, /dashboard, /panel
            if command in ("/admin", "/dashboard", "/panel"):
                if admin_chats:
                    text, markup = build_main_menu(admin_chats, user_first_name=msg.from_user.first_name)
                    await send_message(chat_id=msg.chat.id, text=text, reply_markup=markup)
                    return {"handled": True, "type": "private_message", "is_admin": True}
                else:
                    await send_message(
                        chat_id=msg.chat.id,
                        text="⛔ <b>Access Restricted</b>\n\nYou are not recognized as an administrator in any tracked groups.",
                    )
                    return {"handled": True, "type": "private_message", "action": "admin_unauthorized"}

            # If admin and standard /start or /menu command
            if admin_chats:
                text, markup = build_main_menu(admin_chats, user_first_name=msg.from_user.first_name)
                await send_message(chat_id=msg.chat.id, text=text, reply_markup=markup)
                return {"handled": True, "type": "private_message", "is_admin": True}

            # Normal member flow
            active_chats = await repo.get_active_group_chats()
            member_chats = [c for c in active_chats if await is_chat_member_or_admin(repo, c.chat_id, msg.from_user.id)]

            if len(member_chats) == 1:
                target_chat = member_chats[0]
                invite_link = await get_or_create_user_invite_link(
                    repo, target_chat.chat_id, msg.from_user.id, msg.from_user.first_name
                )
                if invite_link:
                    stat = await repo.get_user_invite_stat(target_chat.chat_id, msg.from_user.id)
                    rank = await repo.get_user_rank(target_chat.chat_id, msg.from_user.id)
                    text, markup = build_user_invite_card(
                        chat_title=target_chat.title or "Group",
                        chat_id=target_chat.chat_id,
                        invite_link=invite_link,
                        total_invites=stat.total_invites if stat else 0,
                        rank=rank,
                        is_admin=False,
                    )
                    await send_message(chat_id=msg.chat.id, text=text, reply_markup=markup)
                    return {"handled": True, "type": "private_message", "action": "member_invite_card"}

            elif len(member_chats) > 1:
                text = (
                    f"👋 <b>Welcome, {msg.from_user.first_name}!</b>\n\n"
                    f"Select a group below to get your personal invite link and view your stats:"
                )
                keyboard = [
                    [{"text": f"👥 {c.title or c.chat_id}", "callback_data": f"user_link:{c.chat_id}"}]
                    for c in member_chats
                ]
                await send_message(chat_id=msg.chat.id, text=text, reply_markup={"inline_keyboard": keyboard})
                return {"handled": True, "type": "private_message", "action": "member_chat_picker"}

            else:
                # User is not yet recognized in any active tracked group
                if active_chats:
                    primary_chat = active_chats[0]
                    chat_info = await fetch_chat_info(primary_chat.chat_id)
                    group_title = primary_chat.title or (chat_info.get("title") if chat_info else "Community Group")
                    join_url = (chat_info.get("invite_link") if chat_info else None) or (
                        f"https://t.me/{chat_info.get('username')}" if chat_info and chat_info.get("username") else None
                    )
                    welcome_msg = (
                        f"👋 <b>Welcome, {msg.from_user.first_name}!</b>\n\n"
                        f"I track verified member invites and leaderboards for <b>{group_title}</b>.\n\n"
                        f"To get your personal invite link and start earning invites, please join the group first:\n"
                    )
                    buttons = []
                    if join_url:
                        buttons.append([{"text": f"👉 Join {group_title}", "url": join_url}])
                    buttons.append([{"text": "🔗 Get My Invite Link", "callback_data": f"user_link:{primary_chat.chat_id}"}])
                    await send_message(chat_id=msg.chat.id, text=welcome_msg, reply_markup={"inline_keyboard": buttons})
                    return {"handled": True, "type": "private_message", "action": "not_member_prompt"}
                else:
                    restricted_msg = (
                        f"👋 <b>Welcome, {msg.from_user.first_name}!</b>\n\n"
                        f"No active groups are currently configured.\n\n"
                        f"If you are an administrator, add this bot to your group with 'Invite Users via Link' permission and send <code>/id</code> to get started."
                    )
                    await send_message(chat_id=msg.chat.id, text=restricted_msg)
                    return {"handled": True, "type": "private_message", "action": "no_chats"}

        # 2. Group Messages -> Direct admins and members to DM to keep group chat clean
        raw_text = (msg.text or "").strip()
        first_word = raw_text.split()[0].lower() if raw_text else ""
        command = first_word.split("@")[0]

        if command in ("/invite", "/link", "/myref", "/mystats"):
            bot_username = await get_bot_username()
            deep_link = f"https://t.me/{bot_username}?start=invite_{abs(msg.chat.id)}"
            reply = (
                f"👋 Hi <b>{msg.from_user.first_name if msg.from_user else 'there'}</b>!\n\n"
                f"You can get your own unique, personal invite link and track your invites in private chat.\n\n"
                f"👇 Tap the button below to get your link:"
            )
            markup = {
                "inline_keyboard": [
                    [{"text": "🔗 Get My Invite Link", "url": deep_link}]
                ]
            }
            await send_message(chat_id=msg.chat.id, text=reply, reply_markup=markup)
            return {"handled": True, "type": "group_message", "action": "invite_link_prompt"}

        if command in ("/admin", "/dashboard", "/stats", "/menu", "/start"):
            dm_notice = (
                f"🔒 <b>Admin Control Panel</b>\n\n"
                f"Hi {msg.from_user.first_name if msg.from_user else 'there'}! Administrative statistics, leaderboards, and reports are accessible exclusively in <b>Private Messages</b> to avoid group chat clutter.\n\n"
                f"👉 Please open a direct message with me to view your dashboard."
            )
            await send_message(chat_id=msg.chat.id, text=dm_notice)
            return {"handled": True, "type": "group_message", "action": "admin_prompt"}

        elif command in ("/id", "/chatid", "/chat_id", "/register", "/track"):
            reply = (
                f"📋 <b>Telegram Chat Info</b>\n\n"
                f"• <b>Chat ID:</b> <code>{msg.chat.id}</code>\n"
                f"• <b>Title:</b> {msg.chat.title or 'Group'}\n"
                f"• <b>Type:</b> {msg.chat.type}\n"
                f"• <b>Status:</b> Tracked ✅\n\n"
                f"<i>Members and admins can open a direct message with this bot to get personal invite links and view rankings.</i>"
            )
            await send_message(chat_id=msg.chat.id, text=reply)
            return {"handled": True, "type": "group_message", "action": "chat_info"}

        return {"handled": True, "type": "group_message", "chat_id": msg.chat.id}

    return {"handled": False, "type": "ignored"}


# =============================================================================
# Read Queries (Delegated to TelegramRepository)
# =============================================================================

async def list_chats(
    db: AsyncSession | TelegramRepository,
    limit: int = 50,
    offset: int = 0,
) -> list[TelegramChatOut]:
    """Lists all tracked chats with current active members and total invite counts."""
    repo = _resolve_repo(db)
    domains = await repo.list_chats_with_counts(limit=limit, offset=offset)
    return [
        TelegramChatOut(
            chat_id=d.chat_id,
            title=d.title,
            type=d.type,
            is_active=d.is_active,
            total_members=d.total_members,
            total_invites=d.total_invites,
            created_at=d.created_at,
            updated_at=d.updated_at,
        )
        for d in domains
    ]


async def get_chat(
    db: AsyncSession | TelegramRepository,
    chat_id: int,
) -> TelegramChatOut | None:
    """Retrieves metadata and counters for a single chat."""
    repo = _resolve_repo(db)
    d = await repo.get_chat_with_counts(chat_id=chat_id)
    if not d:
        return None
    return TelegramChatOut(
        chat_id=d.chat_id,
        title=d.title,
        type=d.type,
        is_active=d.is_active,
        total_members=d.total_members,
        total_invites=d.total_invites,
        created_at=d.created_at,
        updated_at=d.updated_at,
    )


async def get_user_invite_stats(
    db: AsyncSession | TelegramRepository,
    chat_id: int,
    user_id: int,
) -> TelegramInviteStat | None:
    """Fetches total invite counter for a specific user in a chat."""
    repo = _resolve_repo(db)
    return await repo.get_user_invite_stat(chat_id=chat_id, user_id=user_id)


async def get_chat_leaderboard(
    db: AsyncSession | TelegramRepository,
    chat_id: int,
    limit: int = 20,
) -> list[TelegramLeaderboardEntry]:
    """Retrieves the top inviters in a specified chat."""
    repo = _resolve_repo(db)
    domains = await repo.get_leaderboard(chat_id=chat_id, limit=limit)
    return [
        TelegramLeaderboardEntry(
            user_id=d.user_id,
            username=d.username,
            first_name=d.first_name,
            total_invites=d.total_invites,
        )
        for d in domains
    ]
