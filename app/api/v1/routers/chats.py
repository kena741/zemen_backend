from typing import Annotated

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.schemas.chat import (
    ChatBulkResult,
    ChatInboxOut,
    ChatMessageOut,
    ChatMessageSend,
    ChatSendBody,
)
from app.api.v1.schemas.common import Page, PageMeta
from app.core.security.deps import RequireAuth
from app.core.services.chat_service import ChatService
from app.persistence.repositories.chat_repo import ChatRepository
from app.persistence.sqlalchemy.deps import get_db

router = APIRouter(prefix="/chats", tags=["Chats"])


def get_chat_service(
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ChatService:
    return ChatService(ChatRepository(db))


@router.get(
    "/unread/count",
    summary="Get total unread incoming messages count",
)
async def get_unread_count(
    ctx: RequireAuth,
    service: Annotated[ChatService, Depends(get_chat_service)],
) -> dict[str, int]:
    actor_id = str(ctx.customer_id or ctx.provider_id or ctx.user_id)
    cnt = await service.get_unread_count(actor_id)
    return {"unreadCount": cnt}


@router.post(
    "/send",
    response_model=ChatMessageOut,
    status_code=status.HTTP_201_CREATED,
    summary="Send a chat message to a recipient",
)
async def send_chat_message(
    body: ChatMessageSend,
    ctx: RequireAuth,
    service: Annotated[ChatService, Depends(get_chat_service)],
) -> ChatMessageOut:
    actor_id = str(ctx.customer_id or ctx.provider_id or ctx.user_id)
    msg = await service.send_message(
        sender_id=actor_id,
        receiver_id=body.receiver_id,
        message=body.message,
        media_url=body.media_url,
        msg_type=body.type or "text",
        chat_id=body.chat_id,
    )
    return ChatMessageOut.model_validate(msg)


@router.get(
    "/inbox",
    response_model=Page[ChatInboxOut],
    operation_id="chats_list_inbox",
    summary="List chat_inbox rows for the caller's linked identities",
)
async def list_inbox(
    ctx: RequireAuth,
    service: Annotated[ChatService, Depends(get_chat_service)],
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
) -> Page[ChatInboxOut]:
    actor_id = str(ctx.customer_id or ctx.provider_id or ctx.user_id)
    rows = await service.list_inbox(user_id=actor_id, limit=limit, offset=offset)
    return Page(
        items=[ChatInboxOut.model_validate(r) for r in rows],
        meta=PageMeta(limit=limit, offset=offset),
    )


@router.get(
    "/{peer_id}/messages",
    response_model=Page[ChatMessageOut],
    operation_id="chats_list_messages",
    summary="List messages between the caller and peer (Realtime remains the live path)",
)
async def list_messages(
    peer_id: str,
    ctx: RequireAuth,
    service: Annotated[ChatService, Depends(get_chat_service)],
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
) -> Page[ChatMessageOut]:
    actor_id = str(ctx.customer_id or ctx.provider_id or ctx.user_id)
    rows = await service.list_conversation(user_id=actor_id, peer_id=peer_id, limit=limit, offset=offset)
    return Page(
        items=[ChatMessageOut.model_validate(r) for r in rows],
        meta=PageMeta(limit=limit, offset=offset),
    )


@router.post(
    "/{peer_id}/messages",
    response_model=ChatMessageOut,
    status_code=status.HTTP_201_CREATED,
    operation_id="chats_send_message",
    summary="Insert a chat row; manage_chat_inbox trigger updates both inbox rows",
)
async def send_message(
    peer_id: str,
    body: ChatSendBody,
    ctx: RequireAuth,
    service: Annotated[ChatService, Depends(get_chat_service)],
) -> ChatMessageOut:
    actor_id = str(ctx.customer_id or ctx.provider_id or ctx.user_id)
    row = await service.send_message(
        sender_id=actor_id,
        receiver_id=peer_id,
        message=body.message,
        media_url=body.media_url,
        msg_type=body.type,
        chat_id=body.chat_id,
    )
    return ChatMessageOut.model_validate(row)


@router.post(
    "/{peer_id}/seen",
    response_model=ChatBulkResult,
    operation_id="chats_mark_seen",
    summary="Mark inbound messages from peer as seen",
)
async def mark_seen(
    peer_id: str,
    ctx: RequireAuth,
    service: Annotated[ChatService, Depends(get_chat_service)],
) -> ChatBulkResult:
    actor_id = str(ctx.customer_id or ctx.provider_id or ctx.user_id)
    await service.mark_seen(user_id=actor_id, peer_id=peer_id)
    return ChatBulkResult(count=1)


@router.delete(
    "/{peer_id}/messages/{chat_id}",
    response_model=ChatBulkResult,
    operation_id="chats_delete_message",
    summary="Delete one message the caller participates in and sync inbox",
)
async def delete_message(
    peer_id: str,
    chat_id: str,
    ctx: RequireAuth,
    service: Annotated[ChatService, Depends(get_chat_service)],
) -> ChatBulkResult:
    actor_id = str(ctx.customer_id or ctx.provider_id or ctx.user_id)
    await service.delete_message(user_id=actor_id, peer_id=peer_id, chat_id=chat_id)
    return ChatBulkResult(count=1)


@router.delete(
    "/{peer_id}",
    response_model=ChatBulkResult,
    operation_id="chats_clear_conversation",
    summary="Delete the conversation and matching inbox rows",
)
async def clear_conversation(
    peer_id: str,
    ctx: RequireAuth,
    service: Annotated[ChatService, Depends(get_chat_service)],
) -> ChatBulkResult:
    actor_id = str(ctx.customer_id or ctx.provider_id or ctx.user_id)
    count = await service.clear_conversation(user_id=actor_id, peer_id=peer_id)
    return ChatBulkResult(count=count)
