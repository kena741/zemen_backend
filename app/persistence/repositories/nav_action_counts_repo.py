"""Repository for aggregating sidebar action counts across all operations."""

from __future__ import annotations

from typing import Any

from sqlalchemy import func, or_, select

from app.domain.settings import NavActionCountsDomain
from app.persistence.sqlalchemy.models.admin import VerifyDocument
from app.persistence.sqlalchemy.models.booking import BookedService, JobRequest
from app.persistence.sqlalchemy.models.catalog import Service
from app.persistence.sqlalchemy.models.finance import WithdrawalHistory


class NavActionCountsRepository:
    def __init__(self, session: Any) -> None:
        self.session = session

    async def get_aggregated_counts(self) -> NavActionCountsDomain:
        # 1. Payouts pending
        stmt_payouts = select(func.count(WithdrawalHistory.id)).where(
            WithdrawalHistory.payment_status.ilike("pending")
        )
        res_payouts = await self.session.execute(stmt_payouts)
        payouts_cnt = int(res_payouts.scalar_one() or 0)

        # 2. Verify docs pending
        stmt_verify = select(func.count(VerifyDocument.id)).where(
            VerifyDocument.is_verify.is_(None)
        )
        res_verify = await self.session.execute(stmt_verify)
        verify_cnt = int(res_verify.scalar_one() or 0)

        # 3. Services pending approval
        stmt_services = select(func.count(Service.id)).where(
            Service.is_archived.isnot(True),
            Service.status.is_(True),
            or_(
                Service.approved.is_(False),
                Service.feature_requested_status.ilike("pending"),
            ),
        )
        res_services = await self.session.execute(stmt_services)
        services_cnt = int(res_services.scalar_one() or 0)

        # 4. Bookings pending
        stmt_bookings = select(func.count(BookedService.id)).where(
            BookedService.status.in_(["pending", "pending_approval"])
        )
        res_bookings = await self.session.execute(stmt_bookings)
        bookings_cnt = int(res_bookings.scalar_one() or 0)

        # 5. Customer Job requests pending
        stmt_job_requests = select(func.count(JobRequest.id)).where(
            JobRequest.status.in_(["pending", "none", None])
        )
        res_job_requests = await self.session.execute(stmt_job_requests)
        job_requests_cnt = int(res_job_requests.scalar_one() or 0)

        return NavActionCountsDomain(
            payout_requests=payouts_cnt,
            verify_documents=verify_cnt,
            approve_services=services_cnt,
            bookings=bookings_cnt,
            job_requests=job_requests_cnt,
        )
