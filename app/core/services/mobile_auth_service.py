"""Core business logic service for Mobile Authentication, Pluggable SMS OTP, and Sessions."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4

from app.config import settings
from app.core.auth.hashing import hash_password, verify_password
from app.core.auth.jwt import create_access_token, generate_refresh_token
from app.core.sms.otp_engine import OtpEngine, get_otp_engine
from app.core.sms.provider import SMSProvider, get_sms_provider
from app.core.utils.phone import normalize_ethiopian_phone
from app.domain.auth import (
    AuthSessionDomain,
    CustomerSignupDomain,
    MobileUserCredentialsDomain,
    ProviderSignupDomain,
)
from app.domain.customer import CustomerDomain
from app.domain.exceptions import (
    AuthenticationError,
    EntityConflictError,
    EntityNotFoundError,
    ValidationError,
)
from app.domain.provider import ProviderDomain
from app.persistence.repositories.customer_repo import CustomerRepository
from app.persistence.repositories.handyman_repo import HandymanRepository
from app.persistence.repositories.mobile_auth_repo import MobileAuthRepository
from app.persistence.repositories.provider_repo import ProviderRepository


class MobileAuthService:
    """Service orchestrating mobile user registration, login, OTP dispatch, and tokens."""

    def __init__(
        self,
        auth_repo: MobileAuthRepository,
        customer_repo: CustomerRepository,
        provider_repo: ProviderRepository,
        handyman_repo: HandymanRepository,
        sms_provider: SMSProvider | None = None,
        otp_engine: OtpEngine | None = None,
    ) -> None:
        self.auth_repo = auth_repo
        self.customer_repo = customer_repo
        self.provider_repo = provider_repo
        self.handyman_repo = handyman_repo
        self.sms_provider = sms_provider or get_sms_provider()
        self.otp_engine = otp_engine or get_otp_engine()

    async def _resolve_or_create_user_for_signup(
        self,
        email: str | None,
        norm_phone: str,
        password: str,
        target_role: str,
    ) -> tuple[UUID, list[str]]:
        """Return (user_id, existing_roles) or create a new User if none exists.

        Allows an existing Customer to attach a Provider profile (and vice versa)
        using the same email/phone when they supply their existing password.
        """
        existing: MobileUserCredentialsDomain | None = None
        if email:
            existing = await self.auth_repo.get_by_email(email)
        if not existing:
            existing = await self.auth_repo.get_by_phone(norm_phone)

        if existing:
            existing_cust = await self.customer_repo.get_by_user_id(existing.id)
            existing_prov = await self.provider_repo.get_by_user_id(existing.id)
            if target_role == "customer" and existing_cust is not None:
                raise EntityConflictError("A customer account with this email or phone is already registered.")
            if target_role == "provider" and existing_prov is not None:
                raise EntityConflictError("A provider account with this email or phone is already registered.")

            if not existing.hashed_password or not verify_password(password, existing.hashed_password):
                raise EntityConflictError(
                    "Email or phone is already registered. Use your existing password to add this role."
                )

            roles: list[str] = []
            if existing_cust:
                roles.append("customer")
            if existing_prov:
                roles.append("provider")
            return existing.id, roles

        user_id = uuid4()
        user_cred = MobileUserCredentialsDomain(
            id=user_id,
            email=email.lower().strip() if email else None,
            phone=norm_phone,
            hashed_password=hash_password(password),
            is_active=True,
            phone_confirmed_at=datetime.now(timezone.utc),
        )
        await self.auth_repo.create_user(user_cred)
        return user_id, []

    async def signup_customer(self, command: CustomerSignupDomain) -> AuthSessionDomain:
        """Register a new customer, persist profile, and issue auth tokens."""
        norm_phone = normalize_ethiopian_phone(command.phone)
        user_id, existing_roles = await self._resolve_or_create_user_for_signup(
            email=command.email,
            norm_phone=norm_phone,
            password=command.password,
            target_role="customer",
        )

        # Create linked customer profile
        customer_id = uuid4()
        customer = CustomerDomain(
            id=customer_id,
            user_id=user_id,
            first_name=command.first_name,
            last_name=command.last_name,
            phone=norm_phone,
            email=command.email,
            country_code=command.country_code or "+251",
            user_name=command.user_name or f"{command.first_name}_{command.last_name}".lower(),
            profile_pic=command.profile_pic,
            fcm_token=command.fcm_token,
            login_type=command.login_type,
            wallet_amount=command.wallet_amount,
            address=command.address,
            signup_source="mobile_signup",
        )
        await self.customer_repo.create_customer(customer)

        roles = list(dict.fromkeys([*existing_roles, "customer"]))
        return await self._issue_session(
            user_id=user_id,
            email=command.email,
            roles=roles,
            customer_id=customer_id,
            user_data={
                "id": str(user_id),
                "email": command.email,
                "phone": norm_phone,
                "first_name": command.first_name,
                "last_name": command.last_name,
                "customer_id": str(customer_id),
            },
        )

    async def signup_provider(self, command: ProviderSignupDomain) -> AuthSessionDomain:
        """Register a new provider, persist profile, and issue auth tokens."""
        norm_phone = normalize_ethiopian_phone(command.phone)
        user_id, existing_roles = await self._resolve_or_create_user_for_signup(
            email=command.email,
            norm_phone=norm_phone,
            password=command.password,
            target_role="provider",
        )

        # Create linked provider profile
        provider_id = uuid4()
        provider = ProviderDomain(
            id=provider_id,
            user_id=user_id,
            email=command.email,
            first_name=command.first_name,
            last_name=command.last_name,
            user_name=command.user_name or f"{command.first_name}_{command.last_name}".lower(),
            phone_number=norm_phone,
            profile_image=command.profile_image,
            country_code=command.country_code or "+251",
            address=command.address,
            category_id=command.category_id,
            profession_id=command.profession_id,
            fcm_token=command.fcm_token,
            active=True,
            activation_paid=False,
            service_tier_max=0,
            signup_source="mobile_signup",
        )
        await self.provider_repo.create_provider(provider)

        roles = list(dict.fromkeys([*existing_roles, "provider"]))
        return await self._issue_session(
            user_id=user_id,
            email=command.email,
            roles=roles,
            provider_id=provider_id,
            user_data={
                "id": str(user_id),
                "email": command.email,
                "phone": norm_phone,
                "first_name": command.first_name,
                "last_name": command.last_name,
                "provider_id": str(provider_id),
            },
        )

    async def login(
        self,
        identifier: str,
        password: str,
        expected_role: str | None = None,
    ) -> AuthSessionDomain:
        """Authenticate user by email or role-scoped phone and return linked session."""
        candidates = await self.auth_repo.list_by_email_or_phone(
            identifier, expected_role=expected_role
        )
        if not isinstance(candidates, list):
            single = await self.auth_repo.get_by_email_or_phone(identifier)
            candidates = [single] if single else []

        if not candidates:
            raise AuthenticationError("Invalid login credentials.")

        matched_user: MobileUserCredentialsDomain | None = None
        saw_inactive = False
        for candidate in candidates:
            if not candidate.hashed_password or not verify_password(password, candidate.hashed_password):
                continue
            if not candidate.is_active:
                saw_inactive = True
                continue
            matched_user = candidate
            break

        if matched_user is None:
            if saw_inactive:
                raise AuthenticationError("This account has been deactivated. Please contact support.")
            raise AuthenticationError("Invalid login credentials.")

        user = matched_user

        # Record sign-in timestamp
        await self.auth_repo.record_sign_in(user.id)

        # Resolve linked roles and entities
        customer = await self.customer_repo.get_by_user_id(user.id)
        provider = await self.provider_repo.get_by_user_id(user.id)
        handyman = await self.handyman_repo.get_by_user_id(user.id)

        roles: list[str] = []
        if customer:
            roles.append("customer")
        if provider:
            roles.append("provider")
        if handyman:
            roles.append("handyman")

        if not roles:
            roles = ["authenticated"]

        if expected_role and expected_role not in roles:
            raise AuthenticationError(f"Account does not possess the required '{expected_role}' role.")

        user_data = {
            "id": str(user.id),
            "email": user.email,
            "phone": user.phone,
            "roles": roles,
        }
        if customer:
            user_data["customer"] = {
                "id": str(customer.id),
                "name": customer.full_name,
                "phone": customer.phone,
            }
        if provider:
            user_data["provider"] = {
                "id": str(provider.id),
                "name": provider.full_name,
                "phone": provider.phone_number,
            }

        return await self._issue_session(
            user_id=user.id,
            email=user.email,
            roles=roles,
            customer_id=customer.id if customer else None,
            provider_id=provider.id if provider else None,
            handyman_id=handyman.id if handyman else None,
            user_data=user_data,
        )

    async def send_phone_otp(
        self,
        phone: str,
        message_prefix: str = "Your verification code is",
        ttl_seconds: int = 300,
        code_length: int = 6,
    ) -> tuple[str, str]:
        """Generate a random OTP, record it, and dispatch via the pluggable SMS provider.

        Returns:
            (verification_id, plain_code)
        """
        norm_phone = normalize_ethiopian_phone(phone)
        code, verification_id = self.otp_engine.generate_otp(
            phone=norm_phone,
            length=code_length,
            ttl_seconds=ttl_seconds,
        )

        success = await self.sms_provider.send_otp(
            recipient=norm_phone,
            code=code,
            message_prefix=message_prefix,
        )

        if not success:
            logger_msg = f"SMS provider failed to deliver OTP to {norm_phone}"
            # Don't fail silently if provider explicitly fails
            raise ValidationError("Failed to dispatch SMS verification code. Please try again.")

        return verification_id, code

    async def verify_phone_otp(
        self,
        phone: str,
        code: str,
        verification_id: str | None = None,
    ) -> bool:
        """Verify the supplied OTP code."""
        norm_phone = normalize_ethiopian_phone(phone)
        is_valid = self.otp_engine.verify_otp(
            phone=norm_phone,
            code=code,
            verification_id=verification_id,
        )
        if not is_valid:
            raise ValidationError("Invalid or expired verification code.")
        return True

    async def send_plain_sms(self, recipient: str, message: str) -> bool:
        """Send a plain text SMS message via the pluggable provider."""
        norm_phone = normalize_ethiopian_phone(recipient)
        return await self.sms_provider.send_sms(norm_phone, message)

    async def reset_password_by_phone(
        self,
        phone: str,
        code: str,
        new_password: str,
        verification_id: str | None = None,
    ) -> bool:
        """Verify OTP and update user's password."""
        norm_phone = normalize_ethiopian_phone(phone)
        # 1. Verify OTP
        is_valid = self.otp_engine.verify_otp(
            phone=norm_phone,
            code=code,
            verification_id=verification_id,
        )
        if not is_valid:
            raise ValidationError("Invalid or expired OTP code.")

        # 2. Lookup user
        user = await self.auth_repo.get_by_phone(norm_phone)
        if not user:
            raise EntityNotFoundError("User", norm_phone)

        # 3. Update password
        new_hash = hash_password(new_password)
        await self.auth_repo.update_password(user.id, new_hash)
        await self.auth_repo.revoke_refresh_tokens(user.id)
        return True

    async def change_password(
        self,
        user_id: UUID,
        old_password: str,
        new_password: str,
    ) -> bool:
        """Update password for an authenticated user after verifying old password."""
        user = await self.auth_repo.get_by_id(user_id)
        if not user or not user.hashed_password:
            raise AuthenticationError("User account not found.")

        if not verify_password(old_password, user.hashed_password):
            raise AuthenticationError("Incorrect current password.")

        new_hash = hash_password(new_password)
        await self.auth_repo.update_password(user_id, new_hash)
        return True

    async def restore_session(self, user_id: UUID) -> AuthSessionDomain:
        """Restore active session and profile links for an authenticated user ID."""
        user = await self.auth_repo.get_by_id(user_id)
        if not user or not user.is_active:
            raise AuthenticationError("User account is inactive or not found.")

        customer = await self.customer_repo.get_by_user_id(user_id)
        provider = await self.provider_repo.get_by_user_id(user_id)
        handyman = await self.handyman_repo.get_by_user_id(user_id)

        roles: list[str] = []
        if customer:
            roles.append("customer")
        if provider:
            roles.append("provider")
        if handyman:
            roles.append("handyman")
        if not roles:
            roles = ["authenticated"]

        user_data = {
            "id": str(user.id),
            "email": user.email,
            "phone": user.phone,
            "roles": roles,
        }

        return await self._issue_session(
            user_id=user.id,
            email=user.email,
            roles=roles,
            customer_id=customer.id if customer else None,
            provider_id=provider.id if provider else None,
            handyman_id=handyman.id if handyman else None,
            user_data=user_data,
        )

    async def logout(self, user_id: UUID) -> None:
        """Invalidate session by revoking active refresh tokens."""
        await self.auth_repo.revoke_refresh_tokens(user_id)

    async def delete_customer_account(self, user_id: UUID, customer_id: UUID) -> bool:
        """Soft-delete customer account and revoke tokens."""
        await self.auth_repo.soft_delete_user(user_id)
        await self.customer_repo.archive(customer_id, True)
        await self.auth_repo.revoke_refresh_tokens(user_id)
        return True

    async def _issue_session(
        self,
        user_id: UUID,
        email: str | None,
        roles: list[str],
        customer_id: UUID | None = None,
        provider_id: UUID | None = None,
        handyman_id: UUID | None = None,
        user_data: dict[str, Any] | None = None,
    ) -> AuthSessionDomain:
        """Issue access token, refresh token, and return populated AuthSessionDomain."""
        primary_role = roles[0] if roles else "authenticated"
        access_token = create_access_token(
            user_id=user_id,
            email=email,
            role=primary_role,
            extra_claims={
                "roles": roles,
                "customer_id": str(customer_id) if customer_id else None,
                "provider_id": str(provider_id) if provider_id else None,
                "handyman_id": str(handyman_id) if handyman_id else None,
            },
        )

        raw_refresh, token_hash = generate_refresh_token()
        expires_at = datetime.now(timezone.utc) + timedelta(days=settings.JWT_REFRESH_TOKEN_EXPIRE_DAYS)
        await self.auth_repo.store_refresh_token(user_id, token_hash, expires_at)

        return AuthSessionDomain(
            user_id=user_id,
            access_token=access_token,
            refresh_token=raw_refresh,
            token_type="bearer",
            expires_in=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES * 60,
            roles=roles,
            customer_id=customer_id,
            provider_id=provider_id,
            handyman_id=handyman_id,
            user=user_data or {},
        )

