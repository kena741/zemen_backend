from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.exception_handler import register_exception_handlers
from app.config import settings, EnvironmentOptions
from app.persistence.sqlalchemy.map_registry import init_mapper


def register_router(app: FastAPI) -> FastAPI:
    from app.api.v1 import api_v1_router

    app.include_router(api_v1_router)
    return app


def create_app() -> FastAPI:
    env_name = EnvironmentOptions(settings.ENVIRONMENT).name
    app = FastAPI(
        title=f"Zemen Service API — {env_name}",
        version="0.1.0",
        description=(
            "Dedicated backend for Zemen Service (customer + provider). "
            "Validates existing Supabase Auth JWTs and uses the shared betegna Postgres schema. "
            "Released mobile clients may continue using PostgREST during migration."
        ),
        openapi_tags=[
            {"name": "Health", "description": "Liveness / readiness"},
            {"name": "Auth", "description": "Session introspection (Supabase JWT)"},
            {"name": "Catalog", "description": "Categories, sub-categories, public services"},
            {"name": "Config", "description": "Banners, taxes, coupons, app/mobile settings"},
            {"name": "Customers", "description": "Customer profile"},
            {"name": "Providers", "description": "Provider profile, bookings, handymen"},
            {"name": "Bookings", "description": "booked_service reads / later lifecycle actions"},
            {"name": "Jobs", "description": "job_request lists"},
            {"name": "Offers", "description": "service_offer lists"},
            {"name": "Reviews", "description": "review_customer reads"},
            {"name": "Notifications", "description": "notification inbox"},
            {"name": "Wallet", "description": "Read-only wallet / withdrawal ledger"},
            {"name": "Payments", "description": "Plan 4 scaffold — Edge Functions remain source of truth"},
            {"name": "Admin", "description": "lolelink-admin: admin-role checks + admin_activity_log on every write"},
        ],
    )

    init_mapper()
    register_router(app)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ALLOWED_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    return register_exception_handlers(app)


__all__ = ["create_app"]
