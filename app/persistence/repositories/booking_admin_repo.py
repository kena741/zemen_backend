"""Repository for Admin Booking queries, joins, and state updates."""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import delete, func, select, update

from app.domain.booking import BookingDetailDomain, BookingWalletLedgerItemDomain
from app.persistence.repositories.base import BaseRepository
from app.persistence.sqlalchemy.models.booking import BookedService
from app.persistence.sqlalchemy.models.catalog import Service
from app.persistence.sqlalchemy.models.finance import Payment, WalletTransaction
from app.persistence.sqlalchemy.models.identity import Customer, Provider
from app.persistence.sqlalchemy.models.social import Notification


class BookingAdminRepository(BaseRepository[BookedService, BookingDetailDomain]):
    model = BookedService

    def to_domain(
        self,
        entity: BookedService,
        customer_name: str | None = None,
        customer_phone: str | None = None,
        customer_email: str | None = None,
        provider_name: str | None = None,
        provider_phone: str | None = None,
        provider_email: str | None = None,
        service_title: str | None = None,
    ) -> BookingDetailDomain:
        cust_name = customer_name or f"{entity.first_name} {entity.last_name}".strip() or "Customer"
        return BookingDetailDomain(
            id=entity.id,
            provider_id=entity.provider_id,
            customer_id=entity.customer_id,
            service_id=entity.service_id,
            service_name=service_title or entity.service_name,
            customer_name=cust_name,
            customer_phone=customer_phone or entity.phone_number,
            customer_email=customer_email or entity.email,
            provider_name=provider_name or "Provider",
            provider_phone=provider_phone,
            provider_email=provider_email,
            price=float(entity.price or 0.0),
            total_amount=float(entity.total_amount or entity.price or 0.0),
            quantity=entity.quantity,
            booking_date=entity.booking_date,
            payment_completed=entity.payment_completed,
            payment_status=entity.payment_status,
            payment_type=entity.payment_type,
            status=entity.status,
            description=entity.description,
            booking_address=entity.booking_address,
            admin_commission=float(entity.admin_commission) if entity.admin_commission is not None else None,
            admin_note=entity.admin_note,
            is_archived=entity.is_archived,
            created_at=entity.created_at,
        )

    async def list_bookings(
        self,
        statuses: list[str] | None = None,
        include_archived: bool = False,
        offset: int = 0,
        limit: int = 50,
    ) -> list[BookingDetailDomain]:
        stmt = (
            select(
                BookedService,
                Provider.first_name.label("p_first"),
                Provider.last_name.label("p_last"),
                Provider.user_name.label("p_user"),
                Provider.phone_number.label("p_phone"),
                Provider.email.label("p_email"),
                Customer.first_name.label("c_first"),
                Customer.last_name.label("c_last"),
                Customer.phone.label("c_phone"),
                Customer.email.label("c_email"),
                Service.service_name.label("srv_name"),
            )
            .outerjoin(Provider, BookedService.provider_id == Provider.id)
            .outerjoin(Customer, BookedService.customer_id == Customer.id)
            .outerjoin(Service, BookedService.service_id == Service.id)
        )

        if not include_archived:
            stmt = stmt.where(BookedService.is_archived.is_(False))
        if statuses:
            stmt = stmt.where(BookedService.status.in_(statuses))

        stmt = stmt.order_by(BookedService.created_at.desc()).offset(offset).limit(limit)
        res = await self.session.execute(stmt)

        items: list[BookingDetailDomain] = []
        for (
            b,
            p_first,
            p_last,
            p_user,
            p_phone,
            p_email,
            c_first,
            c_last,
            c_phone,
            c_email,
            srv_name,
        ) in res.all():
            prov_name = f"{p_first or ''} {p_last or ''}".strip() or p_user or "Provider"
            cust_name = f"{c_first or ''} {c_last or ''}".strip() or f"{b.first_name} {b.last_name}".strip() or "Customer"
            items.append(
                self.to_domain(
                    b,
                    customer_name=cust_name,
                    customer_phone=c_phone,
                    customer_email=c_email,
                    provider_name=prov_name,
                    provider_phone=p_phone,
                    provider_email=p_email,
                    service_title=srv_name,
                )
            )
        return items

    async def get_by_id_enriched(self, booking_id: UUID) -> BookingDetailDomain | None:
        stmt = (
            select(
                BookedService,
                Provider.first_name.label("p_first"),
                Provider.last_name.label("p_last"),
                Provider.user_name.label("p_user"),
                Provider.phone_number.label("p_phone"),
                Provider.email.label("p_email"),
                Customer.first_name.label("c_first"),
                Customer.last_name.label("c_last"),
                Customer.phone.label("c_phone"),
                Customer.email.label("c_email"),
                Service.service_name.label("srv_name"),
            )
            .outerjoin(Provider, BookedService.provider_id == Provider.id)
            .outerjoin(Customer, BookedService.customer_id == Customer.id)
            .outerjoin(Service, BookedService.service_id == Service.id)
            .where(BookedService.id == booking_id)
        )
        res = await self.session.execute(stmt)
        row = res.first()
        if not row:
            return None
        (
            b,
            p_first,
            p_last,
            p_user,
            p_phone,
            p_email,
            c_first,
            c_last,
            c_phone,
            c_email,
            srv_name,
        ) = row
        prov_name = f"{p_first or ''} {p_last or ''}".strip() or p_user or "Provider"
        cust_name = f"{c_first or ''} {c_last or ''}".strip() or f"{b.first_name} {b.last_name}".strip() or "Customer"
        return self.to_domain(
            b,
            customer_name=cust_name,
            customer_phone=c_phone,
            customer_email=c_email,
            provider_name=prov_name,
            provider_phone=p_phone,
            provider_email=p_email,
            service_title=srv_name,
        )

    async def update_status(
        self,
        booking_id: UUID,
        status: str,
        admin_commission: float | None = None,
    ) -> BookedService | None:
        values: dict[str, Any] = {"status": status}
        if admin_commission is not None:
            values["admin_commission"] = Decimal(str(admin_commission))

        stmt = (
            update(self.model)
            .where(self.model.id == booking_id)
            .values(**values)
            .returning(self.model)
        )
        res = await self.session.execute(stmt)
        return res.scalar_one_or_none()

    async def update_note(
        self,
        booking_id: UUID,
        admin_note: str | None,
    ) -> BookedService | None:
        stmt = (
            update(self.model)
            .where(self.model.id == booking_id)
            .values(admin_note=admin_note)
            .returning(self.model)
        )
        res = await self.session.execute(stmt)
        return res.scalar_one_or_none()

    async def delete_booking_cascade(self, booking_id: UUID) -> bool:
        # Cascade delete from Notification, Payment, BookedService
        await self.session.execute(
            delete(Notification).where(Notification.booking_id == booking_id)
        )
        await self.session.execute(
            delete(Payment).where(Payment.booking_id == booking_id)
        )
        del_b = await self.session.execute(
            delete(self.model).where(self.model.id == booking_id)
        )
        return bool(del_b.rowcount and del_b.rowcount > 0)

    async def mark_payment_completed(
        self,
        booking_id: UUID,
        payment_method: str = "chapa",
        tx_ref: str | None = None,
    ) -> BookedService | None:
        stmt = (
            update(self.model)
            .where(self.model.id == booking_id)
            .values(payment_completed=True, payment_status="paid")
            .returning(self.model)
        )
        res = await self.session.execute(stmt)
        booking = res.scalar_one_or_none()
        if booking:
            # Update payments record if exists
            await self.session.execute(
                update(Payment)
                .where(Payment.booking_id == booking_id)
                .values(status="paid", payment_method=payment_method, provider_ref=tx_ref)
            )
        return booking

    async def get_wallet_ledger_for_booking(
        self, booking_id: UUID
    ) -> list[BookingWalletLedgerItemDomain]:
        stmt = (
            select(WalletTransaction)
            .where(WalletTransaction.transaction_id == str(booking_id))
            .order_by(WalletTransaction.created_date.asc())
        )
        res = await self.session.execute(stmt)
        rows = res.scalars().all()
        return [
            BookingWalletLedgerItemDomain(
                id=r.id,
                amount=r.amount,
                is_credit=r.is_credit,
                note=r.note,
                type=r.type,
                payment_type=r.payment_type,
                created_date=r.created_date,
            )
            for r in rows
        ]

    async def count_pending_badge(self) -> int:
        stmt = select(func.count(self.model.id)).where(
            self.model.is_archived.is_(False),
            self.model.status.in_(["pending", "pending_approval"]),
        )
        res = await self.session.execute(stmt)
        return int(res.scalar_one() or 0)
