from fastapi import APIRouter

from app.api.v1.routers import (
    admin,
    admin_catalog,
    admin_reads,
    auth,
    bookings,
    catalog,
    chats,
    config,
    customers,
    jobs,
    notifications,
    offers,
    payments,
    providers,
    reviews,
    wallet,
)
from app.api.v1.schemas.common import HealthResponse
from app.config import settings, EnvironmentOptions

api_v1_router = APIRouter(prefix="/api/v1")

api_v1_router.include_router(auth.router)
api_v1_router.include_router(catalog.router)
api_v1_router.include_router(config.router)
api_v1_router.include_router(customers.router)
api_v1_router.include_router(providers.router)
api_v1_router.include_router(bookings.router)
api_v1_router.include_router(jobs.router)
api_v1_router.include_router(offers.router)
api_v1_router.include_router(reviews.router)
api_v1_router.include_router(notifications.router)
api_v1_router.include_router(chats.router)
api_v1_router.include_router(wallet.router)
api_v1_router.include_router(payments.router)
api_v1_router.include_router(admin.router)
api_v1_router.include_router(admin_catalog.router)
api_v1_router.include_router(admin_reads.router)


@api_v1_router.get(
    "/health",
    response_model=HealthResponse,
    tags=["Health"],
    operation_id="health_check",
)
async def health_check() -> HealthResponse:
    return HealthResponse(
        status="ok",
        environment=EnvironmentOptions(settings.ENVIRONMENT).name,
    )
