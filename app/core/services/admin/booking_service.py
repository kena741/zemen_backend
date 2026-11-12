"""Service for Admin Bookings lifecycle, status transitions, commissions, and payments."""

from __future__ import annotations

import secrets
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4

from fastapi import HTTPException, status

from app.core.notifications.fcm import FCMService, get_fcm_service
from app.core.security.admin_deps import AdminContext
from app.core.services.admin.audit_service import AdminAuditService
from app.domain.booking import (
    BookingDetailDomain,
    BookingTransitionResultDomain,
    BookingWalletLedgerItemDomain,
    CommissionConfigDomain,
)
from app.persistence.repositories.booking_admin_repo import BookingAdminRepository
from app.persistence.repositories.customer_repo import CustomerRepository
from app.persistence.repositories.provider_repo import ProviderRepository
from app.persistence.repositories.service_repo import ServiceRepository
from app.persistence.sqlalchemy.models.booking import BookedService
from app.persistence.sqlalchemy.models.finance import Payment, WalletTransaction
from app.persistence.sqlalchemy.models.identity import Customer, Provider
from app.persistence.sqlalchemy.models.social import Notification


class BookingAdminService:
    def __init__(
        self,
        booking_repo: BookingAdminRepository,
        provider_repo: ProviderRepository,
        customer_repo: CustomerRepository,
        service_repo: ServiceRepository,
        audit_service: AdminAuditService,
        fcm_service: FCMService | None = None,
    ) -> None:
        self.booking_repo = booking_repo
        self.provider_repo = provider_repo
        self.customer_repo = customer_repo
        self.service_repo = service_repo
        self.audit_service = audit_service
        self.fcm_service = fcm_service or get_fcm_service()

    async def list_bookings(
        self,
        statuses: list[str] | None = None,
        include_archived: bool = False,
        offset: int = 0,
        limit: int = 50,
    ) -> list[BookingDetailDomain]:
        return await self.booking_repo.list_bookings(
            statuses=statuses,
            include_archived=include_archived,
            offset=offset,
            limit=limit,
        )

    async def get_booking(self, booking_id: UUID) -> BookingDetailDomain:
        b = await self.booking_repo.get_by_id_enriched(booking_id)
        if not b:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Booking not found")
        return b

    async def create_booking(
        self,
        provider_id: UUID,
        service_id: UUID,
        customer_id: UUID,
        booking_date: datetime,
        quantity: int = 1,
        description: str | None = None,
        payment_path: str = "pay_later",
        booking_address: dict[str, Any] | None = None,
        coupon_id: int | None = None,
        coupon_code: str | None = None,
        unit_price: float | None = None,
        ctx: AdminContext | None = None,
    ) -> BookingDetailDomain:
        provider = await self.provider_repo.get_by_id(provider_id)
        if not provider:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Provider not found")

        customer, _ = await self.customer_repo.get_by_id(customer_id), None
        if not customer:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Customer not found")

        service = await self.service_repo.get_by_id(service_id)
        if not service:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Service not found")

        price_val = unit_price if unit_price is not None else float(service.price)
        total_amt = round(price_val * quantity, 2)

        payment_completed = False
        payment_status_val = "pending"
        now = datetime.now(timezone.utc)
        booking_id = uuid4()
        payment_id = uuid4()

        if payment_path == "wallet":
            if (customer.wallet_amount or 0.0) < total_amt:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Insufficient wallet balance. Required: {total_amt}, Available: {customer.wallet_amount}",
                )
            new_bal = round(float(customer.wallet_amount or 0.0) - total_amt, 2)
            await self.customer_repo.update(customer_id, {"wallet_amount": Decimal(str(new_bal))})

            tx = WalletTransaction(
                id=uuid4(),
                user_id=customer.user_id,
                customer_id=customer_id,
                amount=str(total_amt),
                is_credit=False,
                payment_type="wallet",
                type="booking_payment",
                transaction_id=str(booking_id),
                note=f"Payment for booking {booking_id}",
                created_date=now,
            )
            self.booking_repo.session.add(tx)
            payment_completed = True
            payment_status_val = "paid"
        elif payment_path == "mark_paid":
            payment_completed = True
            payment_status_val = "paid"

        # Create BookedService entity
        booking_entity = BookedService(
            id=booking_id,
            provider_id=provider_id,
            customer_id=customer_id,
            service_id=service_id,
            payment_id=payment_id,
            service_name=service.service_name,
            first_name=customer.first_name,
            last_name=customer.last_name,
            phone_number=customer.phone,
            email=customer.email,
            price=Decimal(str(price_val)),
            total_amount=Decimal(str(total_amt)),
            sub_total=Decimal(str(total_amt)),
            quantity=quantity,
            booking_date=booking_date,
            payment_completed=payment_completed,
            payment_status=payment_status_val,
            payment_type=payment_path,
            status="pending",
            description=description,
            booking_address=booking_address,
            tax_list=[],
            created_at=now,
            is_archived=False,
        )
        self.booking_repo.session.add(booking_entity)

        # Create Payment entity
        payment_entity = Payment(
            id=payment_id,
            booking_id=booking_id,
            customer_id=customer_id,
            amount=Decimal(str(total_amt)),
            currency="ETB",
            status=payment_status_val,
            payment_method=payment_path,
            created_at=now,
            updated_at=now,
        )
        self.booking_repo.session.add(payment_entity)

        # In-app notification to provider
        notif = Notification(
            id=uuid4(),
            booking_id=booking_id,
            provider_id=provider_id,
            recipient_role="provider",
            title="New Booking Request",
            description=f"New booking received for {service.service_name}",
            type="booking_created",
            is_read=False,
            created_at=now,
        )
        self.booking_repo.session.add(notif)
        await self.booking_repo.session.flush()

        if provider.fcm_token:
            await self.fcm_service.send_to_token(
                token=provider.fcm_token,
                title="New Booking Request",
                body=f"New booking received for {service.service_name}",
                data={"route": f"/bookings/{booking_id}", "booking_id": str(booking_id)},
            )

        await self.audit_service.log_action(
            action="create",
            resource_type="booking",
            resource_id=str(booking_id),
            summary=f"Created booking of {total_amt} ETB for {service.service_name}",
            ctx=ctx,
        )

        return await self.get_booking(booking_id)

    async def update_status(
        self,
        booking_id: UUID,
        new_status: str,
        apply_commission: bool = True,
        commission_percent: float | None = 10.0,
        notify_provider: bool = True,
        notify_customer: bool = True,
        ctx: AdminContext | None = None,
    ) -> BookingTransitionResultDomain:
        booking = await self.get_booking(booking_id)
        if booking.status == new_status:
            return BookingTransitionResultDomain(ok=True, status=new_status, unchanged=True)

        now = datetime.now(timezone.utc)
        provider_payout: float | None = None
        customer_refund: float | None = None
        admin_comm: float | None = None

        if new_status == "completed":
            comm_rate = min(100.0, max(0.0, commission_percent if commission_percent is not None else 10.0))
            admin_comm = round(booking.total_amount * (comm_rate / 100.0), 2) if apply_commission else 0.0
            payout = round(booking.total_amount - admin_comm, 2)
            provider_payout = payout

            # Credit provider wallet
            prov = await self.provider_repo.get_by_id(booking.provider_id)
            if prov:
                try:
                    cur_amt = float(prov.wallet_amount or 0.0)
                except (ValueError, TypeError):
                    cur_amt = 0.0
                new_prov_bal = round(cur_amt + payout, 2)
                await self.provider_repo.update(booking.provider_id, {"wallet_amount": str(new_prov_bal)})

                tx = WalletTransaction(
                    id=uuid4(),
                    user_id=prov.user_id,
                    provider_id=booking.provider_id,
                    amount=str(payout),
                    is_credit=True,
                    payment_type="payout",
                    type="booking_payout",
                    transaction_id=str(booking_id),
                    note=f"Payout for completed booking {booking_id} (Commission: {admin_comm} ETB)",
                    created_date=now,
                )
                self.booking_repo.session.add(tx)

            await self.booking_repo.update_status(booking_id, new_status, admin_commission=admin_comm)

        elif new_status == "rejected":
            if booking.payment_completed and booking.customer_id:
                customer = await self.customer_repo.get_by_id(booking.customer_id)
                if customer:
                    cur_cust_bal = float(customer.wallet_amount or 0.0)
                    new_cust_bal = round(cur_cust_bal + booking.total_amount, 2)
                    customer_refund = booking.total_amount
                    await self.customer_repo.update(
                        booking.customer_id, {"wallet_amount": Decimal(str(new_cust_bal))}
                    )

                    tx = WalletTransaction(
                        id=uuid4(),
                        user_id=customer.user_id,
                        customer_id=booking.customer_id,
                        amount=str(booking.total_amount),
                        is_credit=True,
                        payment_type="refund",
                        type="booking_refund",
                        transaction_id=str(booking_id),
                        note=f"Refund for rejected booking {booking_id}",
                        created_date=now,
                    )
                    self.booking_repo.session.add(tx)

            await self.booking_repo.update_status(booking_id, new_status)

        else:
            await self.booking_repo.update_status(booking_id, new_status)

        # Notify via FCM if enabled
        if notify_provider:
            prov = await self.provider_repo.get_by_id(booking.provider_id)
            if prov and prov.fcm_token:
                await self.fcm_service.send_to_token(
                    token=prov.fcm_token,
                    title=f"Booking Status: {new_status.replace('_', ' ').capitalize()}",
                    body=f"Booking {booking_id} has been marked as {new_status}.",
                    data={"route": f"/bookings/{booking_id}", "booking_id": str(booking_id)},
                )

        if notify_customer and booking.customer_id:
            cust = await self.customer_repo.get_by_id(booking.customer_id)
            if cust and cust.fcm_token:
                await self.fcm_service.send_to_token(
                    token=cust.fcm_token,
                    title=f"Booking Update: {new_status.replace('_', ' ').capitalize()}",
                    body=f"Your booking for {booking.service_name} status is now {new_status}.",
                    data={"route": f"/bookings/{booking_id}", "booking_id": str(booking_id)},
                )

        await self.audit_service.log_action(
            action="update_status",
            resource_type="booking",
            resource_id=str(booking_id),
            summary=f"Updated booking status from '{booking.status}' to '{new_status}'",
            metadata={"new_status": new_status, "payout": provider_payout, "refund": customer_refund},
            ctx=ctx,
        )

        return BookingTransitionResultDomain(
            ok=True,
            status=new_status,
            unchanged=False,
            provider_payout=provider_payout,
            customer_refund=customer_refund,
        )

    async def update_note(
        self,
        booking_id: UUID,
        admin_note: str | None,
        ctx: AdminContext | None = None,
    ) -> BookingDetailDomain:
        updated = await self.booking_repo.update_note(booking_id, admin_note)
        if not updated:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Booking not found")

        await self.audit_service.log_action(
            action="booking.follow_up",
            resource_type="booking",
            resource_id=str(booking_id),
            summary=f"Updated admin follow-up note for booking {booking_id}",
            ctx=ctx,
        )
        return await self.get_booking(booking_id)

    async def delete_booking(
        self,
        booking_id: UUID,
        ctx: AdminContext | None = None,
    ) -> None:
        await self.get_booking(booking_id)
        deleted = await self.booking_repo.delete_booking_cascade(booking_id)
        if not deleted:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Booking not found")

        await self.audit_service.log_action(
            action="delete",
            resource_type="booking",
            resource_id=str(booking_id),
            summary=f"Deleted booking {booking_id}",
            ctx=ctx,
        )

    async def initiate_payment(
        self,
        booking_id: UUID,
        phone_number: str | None = None,
        ctx: AdminContext | None = None,
    ) -> dict[str, Any]:
        b = await self.get_booking(booking_id)
        if b.payment_completed:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Booking payment has already been completed",
            )

        ref = f"bkg-{booking_id.hex[:8]}-{secrets.token_hex(4)}"
        checkout_url = f"https://checkout.chapa.co/checkout/payment/{ref}"

        await self.audit_service.log_action(
            action="initiate_payment",
            resource_type="booking",
            resource_id=str(booking_id),
            summary=f"Initiated Chapa payment ({b.total_amount} ETB) for booking {booking_id}",
            metadata={"tx_ref": ref, "amount": b.total_amount},
            ctx=ctx,
        )

        return {
            "status": "success",
            "checkout_url": checkout_url,
            "tx_ref": ref,
            "booking_id": booking_id,
            "amount": b.total_amount,
        }

    async def verify_payment(
        self,
        booking_id: UUID,
        ctx: AdminContext | None = None,
    ) -> dict[str, Any]:
        b = await self.get_booking(booking_id)
        if b.payment_completed:
            return {
                "status": "success",
                "already_paid": True,
                "booking_id": str(booking_id),
                "message": "Payment already verified",
            }

        await self.booking_repo.mark_payment_completed(booking_id)

        await self.audit_service.log_action(
            action="verify_payment",
            resource_type="booking",
            resource_id=str(booking_id),
            summary=f"Verified payment for booking {booking_id}",
            ctx=ctx,
        )

        return {
            "status": "success",
            "booking_id": str(booking_id),
            "amount": b.total_amount,
            "message": "Payment verified successfully",
        }

    async def recollect_payment(
        self,
        booking_id: UUID,
        mode: str,
        ctx: AdminContext | None = None,
    ) -> dict[str, Any]:
        b = await self.get_booking(booking_id)
        await self.booking_repo.mark_payment_completed(booking_id, payment_method=mode)

        await self.audit_service.log_action(
            action="recollect_payment",
            resource_type="booking",
            resource_id=str(booking_id),
            summary=f"Re-collected payment for booking {booking_id} via {mode}",
            ctx=ctx,
        )

        return {"ok": True, "mode": mode, "amount": b.total_amount}

    async def get_wallet_ledger(
        self, booking_id: UUID
    ) -> list[BookingWalletLedgerItemDomain]:
        await self.get_booking(booking_id)
        return await self.booking_repo.get_wallet_ledger_for_booking(booking_id)

    async def get_commission_config(self) -> CommissionConfigDomain:
        return CommissionConfigDomain(
            default_commission_rate=10.0,
            min_commission_rate=0.0,
            max_commission_rate=100.0,
        )

    async def count_badge(self) -> int:
        return await self.booking_repo.count_pending_badge()
