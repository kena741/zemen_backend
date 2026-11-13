"""Admin Authentication and Session Service."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from uuid import UUID

from fastapi import HTTPException, status

from app.config import settings
from app.core.auth.hashing import verify_password
from app.core.auth.jwt import create_access_token, generate_refresh_token
from app.domain.auth import AdminUserDomain
from app.persistence.repositories.admin_role_repo import AdminRoleRepository
from app.persistence.repositories.admin_user_repo import AdminUserRepository
from app.persistence.sqlalchemy.models.users import UserRefreshToken


@dataclass(frozen=True)
class AdminLoginResult:
    admin: AdminUserDomain
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class AdminAuthService:
    """Manages admin credentials validation and session token generation."""

    def __init__(
        self,
        admin_user_repo: AdminUserRepository,
        admin_role_repo: AdminRoleRepository,
    ) -> None:
        self.admin_user_repo = admin_user_repo
        self.admin_role_repo = admin_role_repo

    async def authenticate_admin(self, email: str, password: str) -> AdminLoginResult:
        """Validate credentials against User + Admin tables and issue JWT pair."""
        lookup = await self.admin_user_repo.get_by_email(email)
        if not lookup:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid email or password",
            )

        admin_domain, user_entity = lookup

        if not user_entity.is_active or not admin_domain.is_active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Admin account is disabled",
            )

        if not user_entity.hashed_password or not verify_password(password, user_entity.hashed_password):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid email or password",
            )

        # Issue access token
        access_token = create_access_token(
            user_id=user_entity.id,
            email=user_entity.email,
            role="authenticated",
            extra_claims={"admin_role": admin_domain.role},
        )

        # Issue refresh token and persist hash
        raw_refresh, token_hash = generate_refresh_token()
        refresh_expires = datetime.now(timezone.utc) + timedelta(
            days=settings.JWT_REFRESH_TOKEN_EXPIRE_DAYS
        )
        refresh_record = UserRefreshToken(
            user_id=user_entity.id,
            token_hash=token_hash,
            expires_at=refresh_expires,
        )
        self.admin_user_repo.session.add(refresh_record)
        await self.admin_user_repo.session.flush()

        return AdminLoginResult(
            admin=admin_domain,
            access_token=access_token,
            refresh_token=raw_refresh,
        )
