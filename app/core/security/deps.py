from __future__ import annotations

from dataclasses import dataclass, field
from typing import Annotated, Literal
from uuid import UUID

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security.supabase_jwt import decode_supabase_token
from app.persistence.sqlalchemy.deps import get_db
from app.persistence.sqlalchemy.models import Customer, Handyman, Provider

bearer = HTTPBearer(auto_error=False)

ActorRole = Literal["customer", "provider", "handyman", "admin", "authenticated"]


@dataclass
class AuthContext:
    """Authenticated caller from Supabase JWT + linked Zemen profiles.

    The merged zemen_service app can attach both customer and provider rows
    to the same auth.users id — never assume a single role.
    """

    user_id: UUID
    email: str | None
    roles: list[ActorRole] = field(default_factory=list)
    customer_id: UUID | None = None
    provider_id: UUID | None = None
    handyman_id: UUID | None = None
    raw_claims: dict | None = None

    def has_role(self, role: ActorRole) -> bool:
        return role in self.roles


def decode_bearer(
    creds: HTTPAuthorizationCredentials | None,
) -> tuple[UUID, str | None, dict]:
    """Validate the Supabase JWT and return (user_id, email, claims)."""
    if creds is None or not creds.credentials:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")

    try:
        claims = decode_supabase_token(creds.credentials)
    except jwt.PyJWTError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token") from exc

    try:
        user_id = UUID(str(claims["sub"]))
    except (KeyError, ValueError) as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid subject") from exc

    email = claims.get("email")
    return user_id, (email if isinstance(email, str) else None), claims


async def get_auth_context(
    creds: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> AuthContext:
    user_id, email_val, claims = decode_bearer(creds)

    customer = (
        await db.execute(
            select(Customer).where(
                Customer.user_id == user_id,
                Customer.archived_at.is_(None),
            )
        )
    ).scalar_one_or_none()

    provider = (
        await db.execute(
            select(Provider).where(
                Provider.user_id == user_id,
                Provider.archived_at.is_(None),
            )
        )
    ).scalar_one_or_none()

    handyman = (
        await db.execute(select(Handyman).where(Handyman.user_id == user_id))
    ).scalar_one_or_none()

    roles: list[ActorRole] = []
    if customer is not None:
        roles.append("customer")
    if provider is not None:
        roles.append("provider")
    if handyman is not None:
        roles.append("handyman")
    if not roles:
        roles.append("authenticated")

    return AuthContext(
        user_id=user_id,
        email=email_val,
        roles=roles,
        customer_id=customer.id if customer else None,
        provider_id=provider.id if provider else None,
        handyman_id=handyman.id if handyman else None,
        raw_claims=claims,
    )


def require_roles(*roles: ActorRole):
    async def _dep(ctx: Annotated[AuthContext, Depends(get_auth_context)]) -> AuthContext:
        if not any(ctx.has_role(r) for r in roles):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")
        return ctx

    return _dep


async def require_customer_profile(ctx: Annotated[AuthContext, Depends(get_auth_context)]) -> AuthContext:
    if ctx.customer_id is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Customer profile required")
    return ctx


async def require_provider_profile(ctx: Annotated[AuthContext, Depends(get_auth_context)]) -> AuthContext:
    if ctx.provider_id is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Provider profile required")
    return ctx


RequireAuth = Annotated[AuthContext, Depends(get_auth_context)]
RequireCustomer = Annotated[AuthContext, Depends(require_customer_profile)]
RequireProvider = Annotated[AuthContext, Depends(require_provider_profile)]
