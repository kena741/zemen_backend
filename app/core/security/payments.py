from fastapi import HTTPException, status

from app.config import settings


def require_payment_writes() -> None:
    if not settings.PAYMENTS_WRITES_ENABLED:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Payment writes are disabled. Edge Functions remain the money writer.",
        )
