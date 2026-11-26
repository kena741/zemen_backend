"""Repository for user authentication credentials and token sessions."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.utils.phone import get_phone_search_variants, normalize_ethiopian_phone
from app.domain.auth import MobileUserCredentialsDomain
from app.persistence.repositories.base import BaseRepository
from app.persistence.sqlalchemy.models.identity import Customer, Provider
from app.persistence.sqlalchemy.models.users import User, UserRefreshToken


class MobileAuthRepository(BaseRepository[User, MobileUserCredentialsDomain]):
    """Async repository managing user persistence and token sessions."""

    model = User

    def to_domain(self, entity: User) -> MobileUserCredentialsDomain:
        return MobileUserCredentialsDomain(
            id=entity.id,
            email=entity.email,
            phone=entity.phone,
            hashed_password=entity.hashed_password,
            is_active=entity.is_active,
            email_confirmed_at=entity.email_confirmed_at,
            phone_confirmed_at=entity.phone_confirmed_at,
        )

    def to_model(self, domain: MobileUserCredentialsDomain) -> User:
        return User(
            id=domain.id,
            email=domain.email.lower() if domain.email else None,
            phone=normalize_ethiopian_phone(domain.phone) if domain.phone else None,
            hashed_password=domain.hashed_password,
            is_active=domain.is_active,
            email_confirmed_at=domain.email_confirmed_at,
            phone_confirmed_at=domain.phone_confirmed_at,
        )

    async def get_by_email(self, email: str) -> MobileUserCredentialsDomain | None:
        """Find active user by email (case-insensitive)."""
        clean_email = email.strip().lower()
        stmt = (
            select(User)
            .where(func.lower(User.email) == clean_email)
            .where(User.deleted_at.is_(None))
        )
        res = await self.session.execute(stmt)
        user = res.scalar_one_or_none()
        return self.to_domain(user) if user else None

    async def get_by_phone(self, phone: str) -> MobileUserCredentialsDomain | None:
        """Find first active user by phone considering Ethiopian variants."""
        variants = get_phone_search_variants(phone)
        stmt = (
            select(User)
            .where(User.phone.in_(variants))
            .where(User.deleted_at.is_(None))
            .order_by(User.created_at.asc())
        )
        res = await self.session.execute(stmt)
        user = res.scalars().first()
        return self.to_domain(user) if user else None

    async def list_by_phone(self, phone: str) -> list[MobileUserCredentialsDomain]:
        """Find all active users matching phone considering Ethiopian variants."""
        variants = get_phone_search_variants(phone)
        stmt = (
            select(User)
            .where(User.phone.in_(variants))
            .where(User.deleted_at.is_(None))
            .order_by(User.created_at.asc())
        )
        res = await self.session.execute(stmt)
        return [self.to_domain(u) for u in res.scalars().all()]

    async def list_users_by_customer_phone(self, phone: str) -> list[MobileUserCredentialsDomain]:
        """Resolve active users linked to a Customer profile with matching phone."""
        variants = get_phone_search_variants(phone)
        stmt = (
            select(User)
            .join(Customer, Customer.user_id == User.id)
            .where(Customer.phone.in_(variants))
            .where(Customer.archived_at.is_(None))
            .where(User.deleted_at.is_(None))
            .order_by(User.created_at.asc())
        )
        res = await self.session.execute(stmt)
        return [self.to_domain(u) for u in res.scalars().all()]

    async def list_users_by_provider_phone(self, phone: str) -> list[MobileUserCredentialsDomain]:
        """Resolve active users linked to a Provider profile with matching phoneNumber."""
        variants = get_phone_search_variants(phone)
        stmt = (
            select(User)
            .join(Provider, Provider.user_id == User.id)
            .where(Provider.phone_number.in_(variants))
            .where(Provider.archived_at.is_(None))
            .where(User.deleted_at.is_(None))
            .order_by(User.created_at.asc())
        )
        res = await self.session.execute(stmt)
        return [self.to_domain(u) for u in res.scalars().all()]

    async def get_by_email_or_phone(self, identifier: str) -> MobileUserCredentialsDomain | None:
        """Find active user by either email or phone."""
        if "@" in identifier:
            return await self.get_by_email(identifier)
        return await self.get_by_phone(identifier)

    async def list_by_email_or_phone(
        self,
        identifier: str,
        expected_role: str | None = None,
    ) -> list[MobileUserCredentialsDomain]:
        """Resolve candidate users for email or role-scoped phone login."""
        if "@" in identifier:
            user = await self.get_by_email(identifier)
            return [user] if user else []

        if expected_role == "customer":
            users = await self.list_users_by_customer_phone(identifier)
            return users or await self.list_by_phone(identifier)
        if expected_role == "provider":
            users = await self.list_users_by_provider_phone(identifier)
            return users or await self.list_by_phone(identifier)
        return await self.list_by_phone(identifier)

    async def create_user(
        self,
        domain: MobileUserCredentialsDomain,
    ) -> MobileUserCredentialsDomain:
        """Create a new user record."""
        user = self.to_model(domain)
        self.session.add(user)
        await self.session.flush()
        return self.to_domain(user)

    async def update_password(self, user_id: UUID, hashed_password: str) -> bool:
        """Update password hash for a user."""
        stmt = (
            update(User)
            .where(User.id == user_id)
            .values(hashed_password=hashed_password, updated_at=func.now())
        )
        res = await self.session.execute(stmt)
        await self.session.flush()
        return res.rowcount > 0

    async def mark_phone_confirmed(self, user_id: UUID) -> None:
        """Mark user's phone number as confirmed."""
        stmt = (
            update(User)
            .where(User.id == user_id)
            .values(phone_confirmed_at=func.now(), updated_at=func.now())
        )
        await self.session.execute(stmt)
        await self.session.flush()

    async def record_sign_in(self, user_id: UUID) -> None:
        """Record last sign-in timestamp."""
        stmt = (
            update(User)
            .where(User.id == user_id)
            .values(last_sign_in_at=func.now())
        )
        await self.session.execute(stmt)
        await self.session.flush()

    async def store_refresh_token(
        self,
        user_id: UUID,
        token_hash: str,
        expires_at: datetime,
    ) -> None:
        """Store hashed refresh token for session tracking."""
        token_row = UserRefreshToken(
            id=uuid4(),
            user_id=user_id,
            token_hash=token_hash,
            expires_at=expires_at,
        )
        self.session.add(token_row)
        await self.session.flush()

    async def revoke_refresh_tokens(self, user_id: UUID) -> None:
        """Revoke all active refresh tokens for user upon sign out."""
        stmt = (
            update(UserRefreshToken)
            .where(UserRefreshToken.user_id == user_id)
            .where(UserRefreshToken.revoked_at.is_(None))
            .values(revoked_at=func.now())
        )
        await self.session.execute(stmt)
        await self.session.flush()

    async def soft_delete_user(self, user_id: UUID) -> bool:
        """Soft-delete user by setting deleted_at and deactivating."""
        stmt = (
            update(User)
            .where(User.id == user_id)
            .values(
                is_active=False,
                deleted_at=func.now(),
                updated_at=func.now(),
            )
        )
        res = await self.session.execute(stmt)
        await self.session.flush()
        return res.rowcount > 0

