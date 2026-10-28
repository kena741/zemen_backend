from typing import Annotated

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.schemas.chat import ChatBulkResult, ChatInboxOut, ChatMessageOut, ChatSendBody
from app.api.v1.schemas.common import Page, PageMeta
from app.core.security.deps import RequireAuth
from app.core.services import chat_service
from app.persistence.sqlalchemy.deps import get_db

router = APIRouter(prefix="/chats", tags=["Chats"])


@router.get(
    "/inbox",
    response_model=Page[ChatInboxOut],
    operation_id="chats_list_inbox",
    summary="List chat_inbox rows for the caller's linked identities",
)
async def list_inbox(
    ctx: RequireAuth,
    db: Annotated[AsyncSession, Depends(get_db)],
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
) -> Page[ChatInboxOut]:
    rows = await chat_service.list_inbox(db, ctx=ctx, limit=limit, offset=offset)
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
    db: Annotated[AsyncSession, Depends(get_db)],
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
) -> Page[ChatMessageOut]:
    rows = await chat_service.list_messages(db, ctx=ctx, peer_id=peer_id, limit=limit, offset=offset)
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
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ChatMessageOut:
    row = await chat_service.send_message(
        db,
        ctx=ctx,
        peer_id=peer_id,
        sender_id=body.sender_id,
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
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ChatBulkResult:
    count = await chat_service.mark_seen(db, ctx=ctx, peer_id=peer_id)
    return ChatBulkResult(count=count)


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
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ChatBulkResult:
    await chat_service.delete_message(db, ctx=ctx, peer_id=peer_id, chat_id=chat_id)
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
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ChatBulkResult:
    count = await chat_service.clear_conversation(db, ctx=ctx, peer_id=peer_id)
    return ChatBulkResult(count=count)
