"""Mobile-specific repository for BookedService queries, upserts (setOrder), and lifecycle actions."""

from __future__ import annotations

import calendar
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import and_, delete, extract, func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.booking import BookingDomain, MonthlyEarningsDomain
from app.persistence.repositories.base import BaseRepository
from app.persistence.sqlalchemy.models.booking import BookedService
from app.persistence.sqlalchemy.models.finance import Payment, WalletTransaction
from app.persistence.sqlalchemy.models.identity import Customer, Handyman, Provider


class MobileBookingRepository(BaseRepository[BookedService, BookingDomain]):
    model = BookedService

    def to_domain(
        self,
        entity: BookedService,
        customer_name: str | None = None,
        provider_name: str | None = None,
        handyman_name: str | None = None,
    ) -> BookingDomain:
        cust_name = (
            customer_name
            or f"{entity.first_name} {entity.last_name}".strip()
            or "Customer"
        )
        return BookingDomain(
            id=entity.id,
            provider_id=entity.provider_id,
            customer_id=entity.customer_id,
            service_id=entity.service_id,
            handyman_id=entity.handyman_id,
            payment_id=entity.payment_id,
            provider_user_id=entity.provider_user_id,
            customer_user_id=entity.customer_user_id,
            service_name=entity.service_name,
            first_name=entity.first_name,
            last_name=entity.last_name,
            email=entity.email,
            phone_number=entity.phone_number,
            price=float(entity.price) if entity.price is not None else None,
            discount=entity.discount,
            total_amount=float(entity.total_amount) if entity.total_amount is not None else None,
            sub_total=float(entity.sub_total) if entity.sub_total is not None else None,
            tax_list=entity.tax_list or [],
            quantity=entity.quantity,
            booking_date=entity.booking_date,
            payment_completed=entity.payment_completed,
            payment_status=entity.payment_status,
            payment_type=entity.payment_type,
            status=entity.status,
            reason=entity.reason,
            country_code=entity.country_code,
            is_archived=entity.is_archived,
            pre_payment_extra_charge_payment=entity.pre_payment_extra_charge_payment,
            post_job_payment=entity.post_job_payment,
            provider_myself=entity.provider_myself,
            description=entity.description,
            service_image=entity.service_image,
            booking_address=entity.booking_address,
            service_details=entity.service_details,
            service_proof=entity.service_proof,
            service_proof_updated_at=entity.service_proof_updated_at,
            otp=entity.otp,
            start_time=entity.start_time,
            end_time=entity.end_time,
            hold_time=entity.hold_time,
            extra_charge_amount=entity.extra_charge_amount,
            extra_charge_gst=entity.extra_charge_gst,
            extra_charge_model=entity.extra_charge_model,
            post_job=entity.post_job,
            coupon=entity.coupon,
            current_period_start=entity.current_period_start,
            current_period_end=entity.current_period_end,
            next_cycle_due=entity.next_cycle_due,
            next_cycle_notified_at=entity.next_cycle_notified_at,
            created_at=entity.created_at,
            customer_name=cust_name,
            provider_name=provider_name,
            handyman_name=handyman_name,
        )

    async def get_by_id_enriched(self, booking_id: UUID) -> BookingDomain | None:
        stmt = (
            select(
                BookedService,
                func.concat(Customer.first_name, " ", Customer.last_name).label("cust_name"),
                func.concat(Provider.first_name, " ", Provider.last_name).label("prov_name"),
                func.concat(Handyman.first_name, " ", Handyman.last_name).label("hm_name"),
            )
            .outerjoin(Customer, BookedService.customer_id == Customer.id)
            .outerjoin(Provider, BookedService.provider_id == Provider.id)
            .outerjoin(Handyman, BookedService.handyman_id == Handyman.id)
            .where(BookedService.id == booking_id)
        )
        res = await self.session.execute(stmt)
        row = res.first()
        if not row:
            return None
        entity, cust_name, prov_name, hm_name = row
        return self.to_domain(
            entity,
            customer_name=cust_name.strip() if cust_name else None,
            provider_name=prov_name.strip() if prov_name else None,
            handyman_name=hm_name.strip() if hm_name else None,
        )

    async def upsert_booking(self, payload: dict[str, Any]) -> BookingDomain:
        booking_id = payload.get("id")
        if not booking_id:
            booking_id = uuid4()
        elif isinstance(booking_id, str):
            booking_id = UUID(booking_id)

        stmt = select(BookedService).where(BookedService.id == booking_id)
        res = await self.session.execute(stmt)
        entity = res.scalar_one_or_none()

        def _to_uuid(val: Any) -> UUID | None:
            if not val:
                return None
            return val if isinstance(val, UUID) else UUID(str(val))

        def _to_decimal(val: Any) -> Decimal | None:
            if val is None or val == "":
                return None
            return Decimal(str(val))

        def _to_dt(val: Any) -> datetime | None:
            if not val:
                return None
            if isinstance(val, datetime):
                return val
            if isinstance(val, str):
                return datetime.fromisoformat(val.replace("Z", "+00:00"))
            return None

        if entity is None:
            now = datetime.now(timezone.utc)
            entity = BookedService(
                id=booking_id,
                provider_id=_to_uuid(payload["provider_id"]),
                customer_id=_to_uuid(payload.get("customer_id")),
                service_id=_to_uuid(payload.get("service_id")),
                handyman_id=_to_uuid(payload.get("handyman_id")),
                payment_id=_to_uuid(payload.get("payment_id")),
                provider_user_id=_to_uuid(payload.get("provider_user_id")),
                customer_user_id=_to_uuid(payload.get("customer_user_id")),
                service_name=payload.get("service_name"),
                first_name=payload.get("first_name", "Customer"),
                last_name=payload.get("last_name", ""),
                email=payload.get("email"),
                phone_number=payload.get("phone_number", ""),
                price=_to_decimal(payload.get("price")),
                discount=str(payload.get("discount")) if payload.get("discount") is not None else None,
                total_amount=_to_decimal(payload.get("total_amount")),
                sub_total=_to_decimal(payload.get("sub_total")),
                tax_list=payload.get("tax_list", []),
                quantity=int(payload.get("quantity", 1)),
                booking_date=_to_dt(payload.get("booking_date")) or now,
                payment_completed=bool(payload.get("payment_completed", False)),
                pre_payment_extra_charge_payment=bool(payload.get("pre_payment_extra_charge_payment", False)),
                post_job_payment=bool(payload.get("post_job_payment", False)),
                provider_myself=bool(payload.get("provider_myself", False)),
                description=payload.get("description"),
                service_image=payload.get("service_image"),
                created_at=_to_dt(payload.get("created_at")) or now,
                booking_address=payload.get("booking_address"),
                service_details=payload.get("service_details"),
                payment_type=payload.get("payment_type"),
                payment_status=payload.get("payment_status", "pending_payment"),
                status=payload.get("status", "pending"),
                reason=payload.get("reason"),
                country_code=payload.get("country_code"),
                is_archived=bool(payload.get("is_archived", False)),
                current_period_start=_to_dt(payload.get("current_period_start")),
                current_period_end=_to_dt(payload.get("current_period_end")),
                next_cycle_due=bool(payload.get("next_cycle_due", False)),
                service_proof=payload.get("service_proof"),
                service_proof_updated_at=_to_dt(payload.get("service_proof_updated_at")),
                otp=payload.get("otp"),
                start_time=_to_dt(payload.get("start_time")),
                end_time=_to_dt(payload.get("end_time")),
                hold_time=payload.get("hold_time"),
                extra_charge_amount=payload.get("extra_charge_amount"),
                extra_charge_gst=payload.get("extra_charge_gst"),
                extra_charge_model=payload.get("extra_charge_model"),
                post_job=payload.get("post_job"),
                coupon=payload.get("coupon"),
            )
            self.session.add(entity)
        else:
            # Update fields present in payload
            for key, val in payload.items():
                if hasattr(entity, key):
                    if key in {"id"}:
                        continue
                    if key.endswith("_id") or key.endswith("_user_id"):
                        setattr(entity, key, _to_uuid(val))
                    elif key in {"price", "total_amount", "sub_total", "admin_commission"}:
                        setattr(entity, key, _to_decimal(val))
                    elif key in {"booking_date", "created_at", "start_time", "end_time", "current_period_start", "current_period_end", "service_proof_updated_at", "next_cycle_notified_at"}:
                        setattr(entity, key, _to_dt(val))
                    else:
                        setattr(entity, key, val)

        await self.session.commit()
        await self.session.refresh(entity)
        return self.to_domain(entity)

    async def list_for_customer(
        self,
        customer_id: UUID,
        status: str | None = None,
        include_archived: bool = False,
        limit: int = 50,
        offset: int = 0,
    ) -> list[BookingDomain]:
        stmt = select(BookedService).where(BookedService.customer_id == customer_id)
        if not include_archived:
            stmt = stmt.where(BookedService.is_archived.is_(False))
        if status:
            stmt = stmt.where(BookedService.status == status)

        stmt = stmt.order_by(BookedService.created_at.desc()).limit(limit).offset(offset)
        res = await self.session.execute(stmt)
        return [self.to_domain(e) for e in res.scalars().all()]

    async def list_for_provider(
        self,
        provider_id: UUID,
        status: str | None = None,
        is_upcoming: bool = False,
        is_completed: bool = False,
        include_archived: bool = False,
        limit: int = 50,
        offset: int = 0,
    ) -> list[BookingDomain]:
        stmt = select(BookedService).where(BookedService.provider_id == provider_id)
        if not include_archived:
            stmt = stmt.where(BookedService.is_archived.is_(False))

        if is_upcoming:
            # Upcoming bookings: status pending, accepted, on_going, hold
            stmt = stmt.where(BookedService.status.in_(["pending", "accepted", "on_going", "hold"]))
        elif is_completed:
            stmt = stmt.where(BookedService.status == "completed")
        elif status:
            stmt = stmt.where(BookedService.status == status)

        stmt = stmt.order_by(BookedService.booking_date.asc(), BookedService.created_at.desc()).limit(limit).offset(offset)
        res = await self.session.execute(stmt)
        return [self.to_domain(e) for e in res.scalars().all()]

    async def delete_unpaid_pending(self, booking_id: UUID, customer_id: UUID) -> bool:
        stmt = (
            delete(BookedService)
            .where(
                BookedService.id == booking_id,
                BookedService.customer_id == customer_id,
                BookedService.payment_completed.is_(False),
                BookedService.status == "pending",
            )
        )
        res = await self.session.execute(stmt)
        await self.session.commit()
        return bool(res.rowcount and res.rowcount > 0)

    async def update_booking_fields(self, booking_id: UUID, fields: dict[str, Any]) -> BookingDomain | None:
        stmt = select(BookedService).where(BookedService.id == booking_id)
        res = await self.session.execute(stmt)
        entity = res.scalar_one_or_none()
        if not entity:
            return None

        for k, v in fields.items():
            if hasattr(entity, k):
                setattr(entity, k, v)

        await self.session.commit()
        await self.session.refresh(entity)
        return self.to_domain(entity)

    async def get_monthly_earnings(
        self, provider_id: UUID, year: int | None = None
    ) -> list[MonthlyEarningsDomain]:
        target_year = year or datetime.now(timezone.utc).year
        stmt = (
            select(
                extract("month", BookedService.booking_date).label("month"),
                func.sum(BookedService.total_amount).label("total"),
                func.count(BookedService.id).label("count"),
            )
            .where(
                BookedService.provider_id == provider_id,
                BookedService.status == "completed",
                BookedService.is_archived.is_(False),
                extract("year", BookedService.booking_date) == target_year,
            )
            .group_by(extract("month", BookedService.booking_date))
            .order_by(extract("month", BookedService.booking_date).asc())
        )
        res = await self.session.execute(stmt)
        out: list[MonthlyEarningsDomain] = []
        for row in res.all():
            m_int = int(row.month)
            out.append(
                MonthlyEarningsDomain(
                    year=target_year,
                    month=m_int,
                    month_name=calendar.month_name[m_int],
                    total_earnings=float(row.total or 0.0),
                    completed_bookings_count=int(row.count or 0),
                )
            )
        return out

    async def get_escrow_amount(self, booking_id: UUID) -> Decimal | None:
        stmt = select(Payment.amount).where(
            Payment.booking_id == booking_id,
            Payment.status == "paid",
        )
        res = await self.session.execute(stmt)
        return res.scalar_one_or_none()

    async def has_refund_transaction(self, booking_id: UUID) -> bool:
        stmt = select(func.count(WalletTransaction.id)).where(
            WalletTransaction.transaction_id == str(booking_id),
            WalletTransaction.type == "customer",
            WalletTransaction.is_credit.is_(True),
        )
        res = await self.session.execute(stmt)
        cnt = res.scalar_one() or 0
        return cnt > 0

    async def credit_customer_wallet_refund(
        self,
        customer_id: UUID,
        customer_user_id: UUID | None,
        booking_id: UUID,
        amount: Decimal,
        note: str,
    ) -> None:
        # 1. Update customer wallet amount
        c_stmt = select(Customer).where(Customer.id == customer_id)
        c_res = await self.session.execute(c_stmt)
        customer = c_res.scalar_one_or_none()
        if customer:
            curr = customer.wallet_amount or Decimal("0.0")
            customer.wallet_amount = curr + amount

        # 2. Add WalletTransaction
        tx = WalletTransaction(
            id=uuid4(),
            customer_id=customer_id,
            user_id=customer_user_id or (customer.user_id if customer else None),
            amount=str(amount),
            is_credit=True,
            type="customer",
            payment_type="wallet",
            transaction_id=str(booking_id),
            note=note,
            created_date=datetime.now(timezone.utc),
        )
        self.session.add(tx)
        await self.session.commit()

    async def upsert_payment_record(
        self,
        booking_id: UUID,
        customer_id: UUID,
        amount: Decimal,
        status: str = "paid",
        payment_method: str = "chapa",
        provider_ref: str | None = None,
    ) -> None:
        stmt = select(Payment).where(Payment.booking_id == booking_id)
        res = await self.session.execute(stmt)
        existing = res.scalar_one_or_none()
        now = datetime.now(timezone.utc)
        if existing:
            existing.amount = amount
            existing.status = status
            existing.payment_method = payment_method
            existing.provider_ref = provider_ref
            existing.updated_at = now
        else:
            pay = Payment(
                id=uuid4(),
                booking_id=booking_id,
                customer_id=customer_id,
                amount=amount,
                currency="ETB",
                status=status,
                payment_method=payment_method,
                provider="chapa",
                provider_ref=provider_ref,
                created_at=now,
                updated_at=now,
            )
            self.session.add(pay)
        await self.session.commit()

