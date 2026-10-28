"""Server-side admin reads replacing lolelink-admin full-table browser selects (Plan 6c)."""

from __future__ import annotations

import re
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import Numeric, and_, case, cast, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.persistence.sqlalchemy.models import (
    BookedService,
    Customer,
    JobRequest,
    Provider,
    ProviderPaymentMethod,
    Service,
    VerifyDocument,
    WalletTransaction,
    WithdrawalHistory,
)


def _like(term: str) -> str:
    escaped = term.strip().replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"%{escaped}%"


def _person(first: str | None, last: str | None, fallback: str | None = None) -> str:
    full = " ".join(p for p in (first, last) if p).strip()
    return full or (fallback or "").strip()


async def _provider_names(db: AsyncSession, ids: set[UUID]) -> dict[UUID, Provider]:
    if not ids:
        return {}
    rows = (await db.execute(select(Provider).where(Provider.id.in_(ids)))).scalars()
    return {p.id: p for p in rows}


# --- Customers --------------------------------------------------------------------------


async def list_customers(
    db: AsyncSession, *, search: str | None, include_archived: bool, limit: int, offset: int
) -> list[dict[str, Any]]:
    stats = (
        select(
            BookedService.customer_id.label("cid"),
            func.count().label("n"),
            func.max(BookedService.created_at).label("last"),
        )
        .group_by(BookedService.customer_id)
        .subquery()
    )
    is_provider = (
        select(Provider.id)
        .where(or_(Provider.id == Customer.id, and_(Customer.user_id.is_not(None), Provider.user_id == Customer.user_id)))
        .exists()
    )
    stmt = select(Customer, stats.c.n, stats.c.last, is_provider.label("is_provider")).outerjoin(
        stats, stats.c.cid == Customer.id
    )
    if not include_archived:
        stmt = stmt.where(Customer.archived_at.is_(None))
    if search:
        pat = _like(search)
        stmt = stmt.where(
            or_(
                Customer.first_name.ilike(pat),
                Customer.last_name.ilike(pat),
                Customer.phone.ilike(pat),
                Customer.email.ilike(pat),
                Customer.user_name.ilike(pat),
            )
        )
    stmt = stmt.order_by(Customer.created_at.desc()).limit(limit).offset(offset)
    return [
        {"row": c, "booking_count": n or 0, "last_booking_at": last, "is_provider": bool(isp)}
        for c, n, last, isp in (await db.execute(stmt)).all()
    ]


# --- Providers --------------------------------------------------------------------------


def _service_count_subquery():
    return (
        select(Service.provider_id.label("pid"), func.count().label("n"))
        .where(Service.is_archived.is_not(True))
        .group_by(Service.provider_id)
        .subquery()
    )


async def list_providers(
    db: AsyncSession,
    *,
    search: str | None,
    active: bool | None,
    include_archived: bool,
    limit: int,
    offset: int,
) -> list[tuple[Provider, int]]:
    counts = _service_count_subquery()
    stmt = select(Provider, counts.c.n).outerjoin(counts, counts.c.pid == Provider.id)
    if not include_archived:
        stmt = stmt.where(Provider.archived_at.is_(None))
    if active is not None:
        stmt = stmt.where(Provider.active.is_(active))
    if search:
        pat = _like(search)
        stmt = stmt.where(
            or_(
                Provider.first_name.ilike(pat),
                Provider.last_name.ilike(pat),
                Provider.user_name.ilike(pat),
                Provider.phone_number.ilike(pat),
                Provider.email.ilike(pat),
            )
        )
    stmt = stmt.order_by(Provider.created_at.desc()).limit(limit).offset(offset)
    return [(p, n or 0) for p, n in (await db.execute(stmt)).all()]


async def get_provider(db: AsyncSession, provider_id: UUID) -> tuple[Provider, int] | None:
    counts = _service_count_subquery()
    row = (
        await db.execute(
            select(Provider, counts.c.n).outerjoin(counts, counts.c.pid == Provider.id).where(Provider.id == provider_id)
        )
    ).first()
    return (row[0], row[1] or 0) if row else None


# --- Services ---------------------------------------------------------------------------

_FEATURE_NOTE = or_(
    WalletTransaction.note.ilike("%featured request%"),
    WalletTransaction.note.ilike("%featured post%"),
    WalletTransaction.note.ilike("%featured psot%"),
    WalletTransaction.note.ilike("%featured%payment%"),
)
_SERVICE_ID_IN_NOTE = re.compile(
    r"service[=:\s]+([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})", re.I
)


async def _featured_payments(db: AsyncSession, pending_ids: set[str]) -> dict[str, dict[str, str | None]]:
    """Match featured-request wallet notes to services (same heuristic as lolelink-admin)."""
    if not pending_ids:
        return {}
    rows = (
        await db.execute(
            select(WalletTransaction.note, WalletTransaction.amount, WalletTransaction.transaction_id)
            .where(_FEATURE_NOTE)
            .order_by(WalletTransaction.created_date.desc().nulls_last())
            .limit(500)
        )
    ).all()
    paid: dict[str, dict[str, str | None]] = {}
    for note, amount, tx in rows:
        note_l = (note or "").lower()
        m = _SERVICE_ID_IN_NOTE.search(note_l)
        sid = m.group(1) if m else next((p for p in pending_ids if p in note_l), None)
        if sid and sid in pending_ids and sid not in paid:
            paid[sid] = {"amount": amount, "transaction_id": tx}
    return paid


async def list_services(
    db: AsyncSession,
    *,
    provider_id: UUID | None,
    include_archived: bool,
    approved: bool | None,
    feature_status: str | None,
    search: str | None,
    limit: int,
    offset: int,
) -> list[dict[str, Any]]:
    stmt = select(Service)
    if provider_id is not None:
        stmt = stmt.where(Service.provider_id == provider_id)
    if not include_archived:
        stmt = stmt.where(Service.status.is_(True), Service.is_archived.is_not(True))
    if approved is not None:
        stmt = stmt.where(Service.approved.is_(approved))
    if feature_status is not None:
        stmt = stmt.where(Service.feature_requested_status == feature_status)
    if search:
        stmt = stmt.where(Service.service_name.ilike(_like(search)))
    stmt = stmt.order_by(Service.created_at.desc()).limit(limit).offset(offset)
    services = list((await db.execute(stmt)).scalars())

    providers = await _provider_names(db, {s.provider_id for s in services})
    pending = {str(s.id) for s in services if s.feature_requested_status == "pending"}
    paid = await _featured_payments(db, pending)

    out = []
    for s in services:
        p = providers.get(s.provider_id)
        pay = paid.get(str(s.id))
        out.append(
            {
                "row": s,
                "provider_name": _person(p.first_name, p.last_name, p.user_name) if p else "",
                "provider_location": p.location if p else None,
                "feature_request_paid": pay is not None,
                "feature_request_paid_amount": pay["amount"] if pay else None,
                "feature_request_transaction_id": pay["transaction_id"] if pay else None,
            }
        )
    return out


# --- Bookings ---------------------------------------------------------------------------


async def _enrich_bookings(db: AsyncSession, rows: list[BookedService]) -> list[dict[str, Any]]:
    providers = await _provider_names(db, {b.provider_id for b in rows})
    cids = {b.customer_id for b in rows if b.customer_id}
    customers = (
        {c.id: c for c in (await db.execute(select(Customer).where(Customer.id.in_(cids)))).scalars()}
        if cids
        else {}
    )
    out = []
    for b in rows:
        p = providers.get(b.provider_id)
        c = customers.get(b.customer_id) if b.customer_id else None
        out.append(
            {
                "row": b,
                "provider_name": _person(p.first_name, p.last_name, p.user_name) if p else None,
                "customer_name": (
                    _person(c.first_name, c.last_name, c.user_name) if c else _person(b.first_name, b.last_name)
                ),
            }
        )
    return out


async def list_bookings(
    db: AsyncSession,
    *,
    statuses: list[str] | None,
    payment_statuses: list[str] | None,
    provider_id: UUID | None,
    customer_id: UUID | None,
    created_from: datetime | None,
    created_to: datetime | None,
    include_archived: bool,
    limit: int,
    offset: int,
) -> list[dict[str, Any]]:
    stmt = select(BookedService)
    if not include_archived:
        stmt = stmt.where(BookedService.is_archived.is_not(True))
    if statuses:
        stmt = stmt.where(BookedService.status.in_(statuses))
    if payment_statuses:
        stmt = stmt.where(BookedService.payment_status.in_(payment_statuses))
    if provider_id is not None:
        stmt = stmt.where(BookedService.provider_id == provider_id)
    if customer_id is not None:
        stmt = stmt.where(BookedService.customer_id == customer_id)
    if created_from is not None:
        stmt = stmt.where(BookedService.created_at >= created_from)
    if created_to is not None:
        stmt = stmt.where(BookedService.created_at < created_to)
    stmt = stmt.order_by(BookedService.created_at.desc()).limit(limit).offset(offset)
    return await _enrich_bookings(db, list((await db.execute(stmt)).scalars()))


async def get_booking(db: AsyncSession, booking_id: UUID) -> dict[str, Any] | None:
    row = (await db.execute(select(BookedService).where(BookedService.id == booking_id))).scalar_one_or_none()
    return (await _enrich_bookings(db, [row]))[0] if row else None


# --- Withdrawals ------------------------------------------------------------------------


async def list_withdrawals(
    db: AsyncSession, *, status: str | None, provider_id: UUID | None, limit: int, offset: int
) -> list[dict[str, Any]]:
    stmt = select(WithdrawalHistory)
    if status is not None:
        stmt = stmt.where(WithdrawalHistory.payment_status == status)
    if provider_id is not None:
        stmt = stmt.where(WithdrawalHistory.provider_id == provider_id)
    stmt = stmt.order_by(WithdrawalHistory.created_date.desc().nulls_last()).limit(limit).offset(offset)
    rows = list((await db.execute(stmt)).scalars())
    providers = await _provider_names(db, {w.provider_id for w in rows if w.provider_id})
    return [
        {
            "row": w,
            "provider_name": (
                _person(providers[w.provider_id].first_name, providers[w.provider_id].last_name)
                if w.provider_id in providers
                else None
            ),
        }
        for w in rows
    ]


async def get_withdrawal(db: AsyncSession, withdrawal_id: UUID) -> dict[str, Any] | None:
    w = (
        await db.execute(select(WithdrawalHistory).where(WithdrawalHistory.id == withdrawal_id))
    ).scalar_one_or_none()
    if w is None:
        return None
    provider = (await _provider_names(db, {w.provider_id})).get(w.provider_id) if w.provider_id else None
    methods = []
    if w.provider_id:
        methods = list(
            (
                await db.execute(
                    select(ProviderPaymentMethod)
                    .where(ProviderPaymentMethod.provider_id == w.provider_id, ProviderPaymentMethod.is_active.is_(True))
                    .order_by(
                        ProviderPaymentMethod.is_default.desc().nulls_last(),
                        ProviderPaymentMethod.updated_at.desc().nulls_last(),
                    )
                )
            ).scalars()
        )
    return {
        "row": w,
        "provider_name": _person(provider.first_name, provider.last_name) if provider else None,
        "payment_methods": methods,
    }


# --- Dashboard --------------------------------------------------------------------------

_NUMERIC_TEXT = r"^\s*-?[0-9]+(\.[0-9]+)?\s*$"


def _since() -> datetime:
    return datetime.now(UTC) - timedelta(days=30)


async def _count_window(db: AsyncSession, model: Any, created_col: Any, *where: Any) -> dict[str, int]:
    since = _since()
    total, recent = (
        await db.execute(
            select(func.count(), func.count().filter(created_col >= since)).select_from(model).where(*where)
        )
    ).one()
    return {"total": total, "last_30_days": recent}


async def dashboard_summary(db: AsyncSession, can: Any) -> dict[str, Any]:
    out: dict[str, Any] = {}
    active_booking = BookedService.is_archived.is_not(True)

    if can("bookings:read"):
        rows = (
            await db.execute(
                select(BookedService.status, func.count()).where(active_booking).group_by(BookedService.status)
            )
        ).all()
        out["bookings_by_status"] = {str(s or "unknown"): n for s, n in rows}
        out["bookings"] = await _count_window(db, BookedService, BookedService.created_at, active_booking)

    if can("customers:read"):
        out["customers"] = await _count_window(db, Customer, Customer.created_at, Customer.archived_at.is_(None))
        out["job_requests"] = await _count_window(db, JobRequest, JobRequest.created_at)

    if can("providers:read"):
        out["providers"] = await _count_window(db, Provider, Provider.created_at, Provider.archived_at.is_(None))

    if can("providers:verify"):
        out["documents_pending"] = (
            await db.execute(select(func.count()).select_from(VerifyDocument).where(VerifyDocument.is_verify.is_(None)))
        ).scalar_one()

    if can("services:read"):
        live = and_(Service.is_archived.is_not(True), Service.status.is_(True))
        pending_approval, pending_feature = (
            await db.execute(
                select(
                    func.count().filter(Service.approved.is_(False)),
                    func.count().filter(Service.feature_requested_status == "pending"),
                ).where(live)
            )
        ).one()
        out["services_pending_approval"] = pending_approval
        out["feature_requests_pending"] = pending_feature

    if can("finance:read"):
        amount = case(
            (WithdrawalHistory.amount.op("~")(_NUMERIC_TEXT), cast(WithdrawalHistory.amount, Numeric)),
            else_=None,
        )
        rows = (
            await db.execute(
                select(WithdrawalHistory.payment_status, func.count()).group_by(WithdrawalHistory.payment_status)
            )
        ).all()
        out["withdrawals_by_status"] = {str(s or "unknown"): n for s, n in rows}
        out["withdrawals_pending_amount"] = (
            await db.execute(select(func.coalesce(func.sum(amount), 0)).where(WithdrawalHistory.payment_status == "pending"))
        ).scalar_one()
        out["completed_booking_revenue"] = (
            await db.execute(
                select(func.coalesce(func.sum(BookedService.total_amount), Decimal(0))).where(
                    active_booking, BookedService.status == "completed", BookedService.payment_completed.is_(True)
                )
            )
        ).scalar_one()

    return out
