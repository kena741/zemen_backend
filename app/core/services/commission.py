from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.persistence.sqlalchemy.models import AppSetting, BookedService


def provider_net(gross: Decimal, *, booking_commission: Decimal | None, rule: dict | None) -> Decimal:
    """Net payout. Treats booking.adminCommission as a numeric amount (not an object)."""
    if gross <= 0:
        return Decimal("0")
    if booking_commission is not None and booking_commission > 0:
        return max(gross - booking_commission, Decimal("0"))
    if not rule:
        return gross
    try:
        value = Decimal(str(rule.get("value") or "0"))
    except Exception:
        return gross
    if rule.get("isFix") is True:
        return max(gross - value, Decimal("0"))
    return max(gross - (gross * value / Decimal("100")), Decimal("0"))


def booking_gross(booking: BookedService) -> Decimal:
    for candidate in (booking.total_amount, booking.sub_total, booking.price):
        if candidate is not None and Decimal(candidate) > 0:
            return Decimal(candidate)
    return Decimal("0")


async def admin_commission_rule(db: AsyncSession) -> dict | None:
    row = (
        await db.execute(select(AppSetting).where(AppSetting.id == "admin_commission"))
    ).scalar_one_or_none()
    if row is None or not isinstance(row.data, dict):
        return None
    return row.data
