"""Admin domain routers."""

from fastapi import APIRouter

from app.api.v1.routers.admin.auth_rbac import router as auth_rbac_router
from app.api.v1.routers.admin.catalog import router as catalog_router
from app.api.v1.routers.admin.customers import router as customers_router
from app.api.v1.routers.admin.legacy import router as legacy_admin_router
from app.api.v1.routers.admin.providers import router as providers_router
from app.api.v1.routers.admin.verification import router as verification_router

admin_v1_router = APIRouter()
admin_v1_router.include_router(auth_rbac_router)
admin_v1_router.include_router(providers_router)
admin_v1_router.include_router(customers_router)
admin_v1_router.include_router(verification_router)
admin_v1_router.include_router(catalog_router)
admin_v1_router.include_router(legacy_admin_router)

# Alias for backward compatibility with `api_v1_router.include_router(admin.router)`
router = admin_v1_router

__all__ = [
    "admin_v1_router",
    "auth_rbac_router",
    "catalog_router",
    "customers_router",
    "legacy_admin_router",
    "providers_router",
    "router",
    "verification_router",
]
