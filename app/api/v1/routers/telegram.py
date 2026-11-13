import logging
import secrets
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.schemas.telegram import (
    TelegramChatOut,
    TelegramInviteStatOut,
    TelegramLeaderboardEntry,
    TelegramWebhookRegistrationResponse,
    TelegramWebhookResponse,
    TelegramWebhookUpdate,
)
from app.config import settings
from app.core.services import telegram_service
from app.persistence.sqlalchemy.deps import get_db

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/telegram", tags=["Telegram"])


async def verify_telegram_secret_token(
    x_telegram_bot_api_secret_token: Annotated[
        str | None,
        Header(alias="X-Telegram-Bot-Api-Secret-Token"),
    ] = None,
) -> None:
    """
    Validates that incoming webhook requests genuinely originate from Telegram.
    Uses constant-time comparison to prevent timing attacks.
    """
    expected_secret = settings.TELEGRAM_WEBHOOK_SECRET

    # If a secret is configured in backend settings, it MUST match the header
    if expected_secret:
        if not x_telegram_bot_api_secret_token:
            logger.warning("Rejected Telegram webhook request: Missing X-Telegram-Bot-Api-Secret-Token header.")
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Missing secret token",
            )

        if not secrets.compare_digest(x_telegram_bot_api_secret_token, expected_secret):
            logger.warning("Rejected Telegram webhook request: Invalid secret token.")
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Invalid secret token",
            )


@router.post(
    "/webhook",
    response_model=TelegramWebhookResponse,
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(verify_telegram_secret_token)],
    operation_id="telegram_receive_webhook",
    summary="Receive webhook updates from Telegram Bot API",
)
async def receive_telegram_webhook(
    update_payload: TelegramWebhookUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> TelegramWebhookResponse:
    """
    Receives Telegram updates. Specifically tracks `chat_member` updates
    to count and credit group/channel member additions and invite link joins.
    """
    try:
        result = await telegram_service.process_telegram_webhook_update(db, update_payload)
        logger.debug("Processed Telegram update %d: %s", update_payload.update_id, result)
        return TelegramWebhookResponse(ok=True)
    except Exception as exc:
        logger.exception("Error processing Telegram update %d: %s", update_payload.update_id, exc)
        # We still return HTTP 200 with ok=False so Telegram does not get stuck in a rapid retry loop,
        # but the failure is logged and observable.
        return TelegramWebhookResponse(ok=False, message=str(exc))


@router.get(
    "/chats",
    response_model=list[TelegramChatOut],
    operation_id="telegram_list_chats",
    summary="List all tracked Telegram chats, groups, and channels with member & invite counts",
)
async def list_telegram_chats(
    db: Annotated[AsyncSession, Depends(get_db)],
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
) -> list[TelegramChatOut]:
    """Lists all groups and channels the bot has been added to or received events from."""
    return await telegram_service.list_chats(db, limit=limit, offset=offset)


@router.get(
    "/chats/{chat_id}",
    response_model=TelegramChatOut,
    operation_id="telegram_get_chat",
    summary="Get details and member/invite counts for a specific chat",
)
async def get_telegram_chat(
    chat_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> TelegramChatOut:
    chat = await telegram_service.get_chat(db, chat_id=chat_id)
    if not chat:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Chat {chat_id} not found in database",
        )
    return chat


@router.get(
    "/stats/{chat_id}/leaderboard",
    response_model=list[TelegramLeaderboardEntry],
    operation_id="telegram_get_chat_leaderboard",
    summary="Get top inviters leaderboard for a specific chat",
)
async def get_chat_leaderboard(
    chat_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    limit: int = Query(20, ge=1, le=100),
) -> list[TelegramLeaderboardEntry]:
    return await telegram_service.get_chat_leaderboard(db, chat_id=chat_id, limit=limit)


@router.get(
    "/stats/{chat_id}/{user_id}",
    response_model=TelegramInviteStatOut,
    operation_id="telegram_get_user_invite_stats",
    summary="Get total invite count for a user in a specific chat",
)
async def get_user_invite_stats(
    chat_id: int,
    user_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> TelegramInviteStatOut:
    stat = await telegram_service.get_user_invite_stats(db, chat_id=chat_id, user_id=user_id)
    if not stat:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No invite statistics found for this user in this chat",
        )
    return TelegramInviteStatOut.model_validate(stat)


@router.post(
    "/register-webhook",
    response_model=TelegramWebhookRegistrationResponse,
    operation_id="telegram_register_webhook_manual",
    summary="Manually trigger Telegram webhook registration",
)
async def register_webhook_endpoint() -> TelegramWebhookRegistrationResponse:
    """Calls Telegram Bot API setWebhook with configured URL, secret, and allowed_updates."""
    return await telegram_service.register_webhook()
