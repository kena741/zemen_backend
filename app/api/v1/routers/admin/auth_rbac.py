"""Admin Authentication, RBAC, and Audit Log Endpoints."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.schemas.admin.requests.auth_rbac import (
    ActivityLogCreateRequest,
    AdminLoginRequest,
    CreateAdminRequest,
    CreateRoleRequest,
    DeleteRoleRequest,
    UpdateAdminRequest,
    UpdateRoleRequest,
)
from app.api.v1.schemas.admin.responses.auth_rbac import (
    ActivityLogListResponse,
    ActivityLogResponseItem,
    AdminLoginData,
    AdminLoginResponse,
    AdminMeData,
    AdminMeResponse,
    AdminOkResponse,
    AdminRoleResponseItem,
    AdminRolesListResponse,
    AdminRoleSingleResponse,
    AdminTokenData,
    AdminUserResponseItem,
    AdminUsersListResponse,
    AdminUserSingleResponse,
)
from app.core.security.admin_deps import AdminContext, RequireAdmin, require_admin_permission
from app.core.services.admin.audit_service import AdminAuditService
from app.core.services.admin.auth_service import AdminAuthService
from app.core.services.admin.role_service import AdminRoleService
from app.core.services.admin.user_service import AdminUserService
from app.persistence.repositories.activity_log_repo import ActivityLogRepository
from app.persistence.repositories.admin_role_repo import AdminRoleRepository
from app.persistence.repositories.admin_user_repo import AdminUserRepository
from app.persistence.sqlalchemy.deps import get_db

router = APIRouter(prefix="/admin", tags=["Admin Auth & RBAC"])

Db = Annotated[AsyncSession, Depends(get_db)]
CanReadRoles = Annotated[AdminContext, Depends(require_admin_permission("roles:read"))]
CanWriteRoles = Annotated[AdminContext, Depends(require_admin_permission("roles:write"))]
CanReadAdmins = Annotated[AdminContext, Depends(require_admin_permission("admins:read"))]
CanWriteAdmins = Annotated[AdminContext, Depends(require_admin_permission("admins:write"))]


def _get_services(db: AsyncSession):
    audit_repo = ActivityLogRepository(db)
    audit_service = AdminAuditService(audit_repo)
    role_repo = AdminRoleRepository(db)
    user_repo = AdminUserRepository(db)
    role_service = AdminRoleService(role_repo, user_repo, audit_service)
    user_service = AdminUserService(user_repo, role_repo, audit_service)
    auth_service = AdminAuthService(user_repo, role_repo)
    return auth_service, role_service, user_service, audit_service


# ---------------------------------------------------------------------------
# Authentication & Identity
# ---------------------------------------------------------------------------


@router.post(
    "/auth/login",
    response_model=AdminLoginResponse,
    operation_id="admin_auth_login",
    summary="Authenticate admin with password",
)
async def admin_login(body: AdminLoginRequest, db: Db) -> AdminLoginResponse:
    auth_service, _, _, _ = _get_services(db)
    result = await auth_service.authenticate_admin(body.email, body.password)
    return AdminLoginResponse(
        data=AdminLoginData(
            admin=AdminMeData(
                admin_id=result.admin.id,
                user_id=result.admin.user_id,
                email=result.admin.email,
                full_name=result.admin.full_name,
                role=result.admin.role,
                permissions=[],  # Hydrated by /me
            ),
            session=AdminTokenData(
                access_token=result.access_token,
                refresh_token=result.refresh_token,
                token_type=result.token_type,
            ),
        )
    )


@router.get(
    "/auth/me",
    response_model=AdminMeResponse,
    operation_id="admin_auth_me",
    summary="Current authenticated admin grants and profile",
)
async def get_current_admin(ctx: RequireAdmin) -> AdminMeResponse:
    return AdminMeResponse(
        data=AdminMeData(
            admin_id=ctx.admin_id,
            user_id=ctx.user_id,
            email=ctx.email,
            full_name=ctx.full_name,
            role=ctx.role,
            permissions=ctx.permissions,
        )
    )


# ---------------------------------------------------------------------------
# RBAC - Roles
# ---------------------------------------------------------------------------


@router.get(
    "/roles",
    response_model=AdminRolesListResponse,
    operation_id="admin_roles_list",
    summary="List all admin roles",
)
async def list_roles(ctx: CanReadRoles, db: Db) -> AdminRolesListResponse:
    _, role_service, _, _ = _get_services(db)
    roles = await role_service.list_roles()
    return AdminRolesListResponse(
        data=[AdminRoleResponseItem.model_validate(r) for r in roles]
    )


@router.post(
    "/roles",
    response_model=AdminRoleSingleResponse,
    operation_id="admin_roles_create",
    status_code=status.HTTP_201_CREATED,
    summary="Create custom admin role",
)
async def create_role(body: CreateRoleRequest, ctx: CanWriteRoles, db: Db) -> AdminRoleSingleResponse:
    _, role_service, _, _ = _get_services(db)
    role = await role_service.create_role(
        slug=body.slug,
        name=body.name,
        permissions=body.permissions,
        description=body.description,
        ctx=ctx,
    )
    return AdminRoleSingleResponse(data=AdminRoleResponseItem.model_validate(role))


@router.patch(
    "/roles",
    response_model=AdminRoleSingleResponse,
    operation_id="admin_roles_update_body",
    summary="Update admin role via body ID",
)
async def update_role_body(body: UpdateRoleRequest, ctx: CanWriteRoles, db: Db) -> AdminRoleSingleResponse:
    if not body.id:
        from fastapi import HTTPException
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Role ID required")
    _, role_service, _, _ = _get_services(db)
    updated = await role_service.update_role(
        role_id=body.id,
        name=body.name,
        description=body.description,
        permissions=body.permissions,
        slug=body.slug,
        ctx=ctx,
    )
    return AdminRoleSingleResponse(data=AdminRoleResponseItem.model_validate(updated))


@router.patch(
    "/roles/{role_id}",
    response_model=AdminRoleSingleResponse,
    operation_id="admin_roles_update_path",
    summary="Update admin role via path ID",
)
async def update_role_path(role_id: UUID, body: UpdateRoleRequest, ctx: CanWriteRoles, db: Db) -> AdminRoleSingleResponse:
    _, role_service, _, _ = _get_services(db)
    updated = await role_service.update_role(
        role_id=role_id,
        name=body.name,
        description=body.description,
        permissions=body.permissions,
        slug=body.slug,
        ctx=ctx,
    )
    return AdminRoleSingleResponse(data=AdminRoleResponseItem.model_validate(updated))


@router.delete(
    "/roles",
    response_model=AdminOkResponse,
    operation_id="admin_roles_delete_body",
    summary="Delete custom admin role via body ID",
)
async def delete_role_body(body: DeleteRoleRequest, ctx: CanWriteRoles, db: Db) -> AdminOkResponse:
    _, role_service, _, _ = _get_services(db)
    await role_service.delete_role(body.id, ctx=ctx)
    return AdminOkResponse()


@router.delete(
    "/roles/{role_id}",
    response_model=AdminOkResponse,
    operation_id="admin_roles_delete_path",
    summary="Delete custom admin role via path ID",
)
async def delete_role_path(role_id: UUID, ctx: CanWriteRoles, db: Db) -> AdminOkResponse:
    _, role_service, _, _ = _get_services(db)
    await role_service.delete_role(role_id, ctx=ctx)
    return AdminOkResponse()


# ---------------------------------------------------------------------------
# RBAC - Admin Accounts
# ---------------------------------------------------------------------------


@router.get(
    "/admins",
    response_model=AdminUsersListResponse,
    operation_id="admin_users_list",
    summary="List all admin users with email",
)
async def list_admins(ctx: CanReadAdmins, db: Db) -> AdminUsersListResponse:
    _, _, user_service, _ = _get_services(db)
    admins = await user_service.list_admins()
    return AdminUsersListResponse(
        data=[AdminUserResponseItem.model_validate(a) for a in admins]
    )


@router.post(
    "/admins",
    response_model=AdminUserSingleResponse,
    operation_id="admin_users_create",
    status_code=status.HTTP_201_CREATED,
    summary="Provision new admin user",
)
async def create_admin(body: CreateAdminRequest, ctx: CanWriteAdmins, db: Db) -> AdminUserSingleResponse:
    _, _, user_service, _ = _get_services(db)
    admin = await user_service.create_admin(
        email=body.email,
        password=body.password,
        full_name=body.full_name,
        role=body.role,
        is_active=body.is_active,
        ctx=ctx,
    )
    return AdminUserSingleResponse(data=AdminUserResponseItem.model_validate(admin))


@router.patch(
    "/admins/{admin_id}",
    response_model=AdminUserSingleResponse,
    operation_id="admin_users_update",
    summary="Update admin account or password",
)
async def update_admin(admin_id: UUID, body: UpdateAdminRequest, ctx: CanWriteAdmins, db: Db) -> AdminUserSingleResponse:
    _, _, user_service, _ = _get_services(db)
    updated = await user_service.update_admin(
        admin_id=admin_id,
        full_name=body.full_name,
        role=body.role,
        is_active=body.is_active,
        password=body.password,
        ctx=ctx,
    )
    return AdminUserSingleResponse(data=AdminUserResponseItem.model_validate(updated))


@router.delete(
    "/admins/{admin_id}",
    response_model=AdminOkResponse,
    operation_id="admin_users_delete",
    summary="Delete admin account",
)
async def delete_admin(admin_id: UUID, ctx: CanWriteAdmins, db: Db) -> AdminOkResponse:
    _, _, user_service, _ = _get_services(db)
    await user_service.delete_admin(admin_id, ctx=ctx)
    return AdminOkResponse()


# ---------------------------------------------------------------------------
# Audit & Activity Logs
# ---------------------------------------------------------------------------


@router.get(
    "/activity-logs",
    response_model=ActivityLogListResponse,
    operation_id="admin_activity_logs_list",
    summary="List searchable admin audit trail",
)
async def list_activity_logs(
    ctx: RequireAdmin,
    db: Db,
    admin_id: UUID | None = None,
    action: str | None = None,
    resource_type: str | None = None,
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
) -> ActivityLogListResponse:
    _, _, _, audit_service = _get_services(db)
    logs, count = await audit_service.list_logs(
        admin_id=admin_id,
        action=action,
        resource_type=resource_type,
        offset=offset,
        limit=limit,
    )
    return ActivityLogListResponse(
        data=[ActivityLogResponseItem.model_validate(item) for item in logs],
        count=count,
    )


@router.post(
    "/activity-logs",
    response_model=AdminOkResponse,
    operation_id="admin_activity_logs_create",
    summary="Submit manual admin activity log entry",
)
async def create_activity_log(
    body: ActivityLogCreateRequest,
    ctx: RequireAdmin,
    db: Db,
) -> AdminOkResponse:
    _, _, _, audit_service = _get_services(db)
    await audit_service.log_action(
        action=body.action,
        resource_type=body.resource_type,
        summary=body.summary,
        ctx=ctx,
        resource_id=body.resource_id,
        route=body.route,
        metadata=body.metadata,
        env=body.env,
    )
    return AdminOkResponse()
