import asyncio
from types import SimpleNamespace
from uuid import uuid4

from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.api import create_app
from app.core.security.deps import AuthContext, get_auth_context
from app.core.services import chat_service
from app.persistence.sqlalchemy.deps import get_db


class _Rows:
    def __init__(self, rows=None, scalar=None):
        self._rows = rows or []
        self._scalar = scalar

    def all(self):
        return self._rows

    def scalars(self):
        return self

    def scalar_one_or_none(self):
        if self._scalar is not None:
            return self._scalar
        return self._rows[0] if self._rows else None


class _Db:
    def __init__(self, results=None):
        self.results = list(results or [])
        self.added = []
        self.deleted = []

    async def execute(self, stmt, _params=None):
        return self.results.pop(0) if self.results else _Rows()

    def add(self, row):
        self.added.append(row)

    async def delete(self, row):
        self.deleted.append(row)

    async def flush(self):
        return None

    async def refresh(self, row):
        return row


def _ctx(*, customer=False, provider=False) -> AuthContext:
    uid = uuid4()
    return AuthContext(
        user_id=uid,
        email="a@b.com",
        roles=(["customer"] if customer else []) + (["provider"] if provider else []) or ["authenticated"],
        customer_id=uid if customer else None,
        provider_id=uid if provider else None,
    )


def _client(ctx: AuthContext | None = None) -> TestClient:
    app = create_app()
    if ctx is not None:
        app.dependency_overrides[get_auth_context] = lambda: ctx

    async def _db():
        yield _Db()

    app.dependency_overrides[get_db] = _db
    return TestClient(app)


def test_chat_routes_require_auth():
    client = TestClient(create_app())
    peer = str(uuid4())
    assert client.get("/api/v1/chats/inbox").status_code == 401
    assert client.get(f"/api/v1/chats/{peer}/messages").status_code == 401
    assert client.post(f"/api/v1/chats/{peer}/messages", json={"message": "hi"}).status_code == 401
    assert client.post(f"/api/v1/chats/{peer}/seen").status_code == 401
    assert client.delete(f"/api/v1/chats/{peer}").status_code == 401


def test_send_forces_caller_sender_and_rejects_self():
    ctx = _ctx(customer=True)
    peer = str(uuid4())
    row = asyncio.run(
        chat_service.send_message(
            _Db(),
            ctx=ctx,
            peer_id=peer,
            sender_id=str(ctx.customer_id),
            message="hello",
            media_url=None,
            msg_type="text",
            chat_id="c1",
        )
    )
    assert row.sender_id == str(ctx.customer_id)
    assert row.receiver_id == peer
    assert row.seen is False
    assert row.message == "hello"

    try:
        asyncio.run(
            chat_service.send_message(
                _Db(),
                ctx=ctx,
                peer_id=str(ctx.customer_id),
                sender_id=str(ctx.customer_id),
                message="nope",
                media_url=None,
                msg_type="text",
                chat_id=None,
            )
        )
        raise AssertionError("expected self-message error")
    except HTTPException as exc:
        assert exc.status_code == 400


def test_send_rejects_forged_sender():
    ctx = _ctx(customer=True)
    try:
        asyncio.run(
            chat_service.send_message(
                _Db(),
                ctx=ctx,
                peer_id=str(uuid4()),
                sender_id=str(uuid4()),
                message="hi",
                media_url=None,
                msg_type="text",
                chat_id=None,
            )
        )
        raise AssertionError("expected forbidden")
    except HTTPException as exc:
        assert exc.status_code == 403


def test_send_requires_body_or_media():
    ctx = _ctx(provider=True)
    try:
        asyncio.run(
            chat_service.send_message(
                _Db(),
                ctx=ctx,
                peer_id=str(uuid4()),
                sender_id=str(ctx.provider_id),
                message="  ",
                media_url="",
                msg_type="text",
                chat_id=None,
            )
        )
        raise AssertionError("expected 400")
    except HTTPException as exc:
        assert exc.status_code == 400


def test_delete_message_requires_participant():
    ctx = _ctx(customer=True)
    row = SimpleNamespace(chat_id="m1", sender_id=str(uuid4()), receiver_id=str(uuid4()))
    db = _Db([_Rows(scalar=row)])
    try:
        asyncio.run(chat_service.delete_message(db, ctx=ctx, peer_id=row.receiver_id, chat_id="m1"))
        raise AssertionError("expected forbidden")
    except HTTPException as exc:
        assert exc.status_code == 403


def test_clear_deletes_messages_and_inbox():
    ctx = _ctx(provider=True)
    peer = str(uuid4())
    msg = SimpleNamespace(chat_id="m1")
    inbox = SimpleNamespace(id=f"{ctx.provider_id}_{peer}")
    db = _Db([_Rows(rows=[msg]), _Rows(rows=[inbox]), _Rows(rows=[])])
    count = asyncio.run(chat_service.clear_conversation(db, ctx=ctx, peer_id=peer))
    assert count == 1
    assert msg in db.deleted
    assert inbox in db.deleted


def test_mark_seen_only_inbound():
    ctx = _ctx(customer=True)
    peer = str(uuid4())
    inbound = SimpleNamespace(sender_id=peer, receiver_id=str(ctx.customer_id), seen=False)
    inbox = SimpleNamespace(id=f"{ctx.customer_id}_{peer}", seen=False)
    db = _Db([_Rows(rows=[inbound]), _Rows(rows=[inbox])])
    count = asyncio.run(chat_service.mark_seen(db, ctx=ctx, peer_id=peer))
    assert count == 1
    assert inbound.seen is True
    assert inbox.seen is True
