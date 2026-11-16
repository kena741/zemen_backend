"""Mobile Authentication, Session, and OTP endpoints."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.schemas.auth import (
    AuthMeResponse,
    AuthSessionResponse,
    ChangePasswordRequest,
    CheckPhoneRequest,
    CustomerSignupRequest,
    LoginRequest,
    OtpSendResponse,
    OtpVerifyResponse,
    PhoneResetPasswordRequest,
    PlainSmsRequest,
    ProviderSignupRequest,
    SendOtpRequest,
    SuccessMessageResponse,
    VerifyOtpRequest,
)
from app.core.security.deps import RequireAuth, RequireCustomer
from app.core.services.mobile_auth_service import MobileAuthService
from app.domain.auth import CustomerSignupDomain, ProviderSignupDomain
from app.domain.exceptions import EntityNotFoundError
from app.persistence.repositories.customer_repo import CustomerRepository
from app.persistence.repositories.handyman_repo import HandymanRepository
from app.persistence.repositories.mobile_auth_repo import MobileAuthRepository
from app.persistence.repositories.provider_repo import ProviderRepository
from app.persistence.sqlalchemy.deps import get_db

router = APIRouter(prefix="/auth", tags=["Auth"])
sms_compat_router = APIRouter(prefix="/sms", tags=["SMS"])


def get_mobile_auth_service(
    db: Annotated[AsyncSession, Depends(get_db)],
) -> MobileAuthService:
    return MobileAuthService(
        auth_repo=MobileAuthRepository(db),
        customer_repo=CustomerRepository(db),
        provider_repo=ProviderRepository(db),
        handyman_repo=HandymanRepository(db),
    )


# ======================== Customer & Provider Registration ========================


@router.post(
    "/signup/customer",
    response_model=AuthSessionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register Customer",
    description="Registers a customer user, creates profile and wallet, and issues JWT tokens.",
)
async def signup_customer(
    body: CustomerSignupRequest,
    service: Annotated[MobileAuthService, Depends(get_mobile_auth_service)],
) -> AuthSessionResponse:
    domain_cmd = CustomerSignupDomain(
        email=body.email,
        password=body.password,
        first_name=body.first_name,
        last_name=body.last_name,
        phone=body.phone,
        user_name=body.user_name,
        country_code=body.country_code,
        address=body.address,
        login_type=body.login_type,
        fcm_token=body.fcm_token,
        profile_pic=body.profile_pic,
    )
    session = await service.signup_customer(domain_cmd)
    return AuthSessionResponse(
        access_token=session.access_token,
        refresh_token=session.refresh_token,
        token_type=session.token_type,
        expires_in=session.expires_in,
        roles=session.roles,
        customer_id=session.customer_id,
        provider_id=session.provider_id,
        handyman_id=session.handyman_id,
        user=session.user,
    )


@router.post(
    "/signup/provider",
    response_model=AuthSessionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register Provider",
    description="Registers a provider user, creates profile, and issues JWT tokens.",
)
async def signup_provider(
    body: ProviderSignupRequest,
    service: Annotated[MobileAuthService, Depends(get_mobile_auth_service)],
) -> AuthSessionResponse:
    domain_cmd = ProviderSignupDomain(
        email=body.email,
        password=body.password,
        first_name=body.first_name,
        last_name=body.last_name,
        phone=body.phone,
        user_name=body.user_name,
        country_code=body.country_code,
        address=body.address,
        category_id=body.category_id,
        profession_id=body.profession_id,
        fcm_token=body.fcm_token,
        profile_image=body.profile_image,
    )
    session = await service.signup_provider(domain_cmd)
    return AuthSessionResponse(
        access_token=session.access_token,
        refresh_token=session.refresh_token,
        token_type=session.token_type,
        expires_in=session.expires_in,
        roles=session.roles,
        customer_id=session.customer_id,
        provider_id=session.provider_id,
        handyman_id=session.handyman_id,
        user=session.user,
    )


# ======================== Login Endpoints ========================


@router.post(
    "/login",
    response_model=AuthSessionResponse,
    summary="User Login",
    description="Authenticate by email or phone and password.",
)
async def login(
    body: LoginRequest,
    service: Annotated[MobileAuthService, Depends(get_mobile_auth_service)],
) -> AuthSessionResponse:
    session = await service.login(
        identifier=body.identifier or body.email or body.phone or "",
        password=body.password,
    )
    return AuthSessionResponse(
        access_token=session.access_token,
        refresh_token=session.refresh_token,
        token_type=session.token_type,
        expires_in=session.expires_in,
        roles=session.roles,
        customer_id=session.customer_id,
        provider_id=session.provider_id,
        handyman_id=session.handyman_id,
        user=session.user,
    )


@router.post(
    "/login/customer",
    response_model=AuthSessionResponse,
    summary="Customer Login",
)
async def login_customer(
    body: LoginRequest,
    service: Annotated[MobileAuthService, Depends(get_mobile_auth_service)],
) -> AuthSessionResponse:
    session = await service.login(
        identifier=body.identifier or body.email or body.phone or "",
        password=body.password,
        expected_role="customer",
    )
    return AuthSessionResponse(
        access_token=session.access_token,
        refresh_token=session.refresh_token,
        token_type=session.token_type,
        expires_in=session.expires_in,
        roles=session.roles,
        customer_id=session.customer_id,
        provider_id=session.provider_id,
        handyman_id=session.handyman_id,
        user=session.user,
    )


@router.post(
    "/login/provider",
    response_model=AuthSessionResponse,
    summary="Provider Login",
)
async def login_provider(
    body: LoginRequest,
    service: Annotated[MobileAuthService, Depends(get_mobile_auth_service)],
) -> AuthSessionResponse:
    session = await service.login(
        identifier=body.identifier or body.email or body.phone or "",
        password=body.password,
        expected_role="provider",
    )
    return AuthSessionResponse(
        access_token=session.access_token,
        refresh_token=session.refresh_token,
        token_type=session.token_type,
        expires_in=session.expires_in,
        roles=session.roles,
        customer_id=session.customer_id,
        provider_id=session.provider_id,
        handyman_id=session.handyman_id,
        user=session.user,
    )


# ======================== Pluggable SMS & OTP ========================


@router.post(
    "/otp/send",
    response_model=OtpSendResponse,
    summary="Send Phone OTP",
    description="Generate and dispatch an OTP via the configured SMS provider.",
)
@sms_compat_router.post("/send-otp", response_model=OtpSendResponse)
@sms_compat_router.post("/secure/send-otp", response_model=OtpSendResponse)
async def send_otp(
    body: SendOtpRequest,
    service: Annotated[MobileAuthService, Depends(get_mobile_auth_service)],
) -> OtpSendResponse:
    target_phone = body.recipient or body.phone or ""
    verification_id, _ = await service.send_phone_otp(
        phone=target_phone,
        message_prefix=body.message_prefix,
        ttl_seconds=body.ttl,
        code_length=body.code_length,
    )
    return OtpSendResponse(
        success=True,
        verification_id=verification_id,
        message="Verification code dispatched successfully.",
    )


@router.post(
    "/otp/verify",
    response_model=OtpVerifyResponse,
    summary="Verify Phone OTP",
)
@sms_compat_router.post("/verify-otp", response_model=OtpVerifyResponse)
@sms_compat_router.post("/secure/verify-otp", response_model=OtpVerifyResponse)
async def verify_otp(
    body: VerifyOtpRequest,
    service: Annotated[MobileAuthService, Depends(get_mobile_auth_service)],
) -> OtpVerifyResponse:
    target_phone = body.recipient or body.phone or ""
    await service.verify_phone_otp(
        phone=target_phone,
        code=body.code,
        verification_id=body.verification_id,
    )
    return OtpVerifyResponse(success=True, message="Verification successful.")


@router.post(
    "/sms/send",
    response_model=SuccessMessageResponse,
    summary="Send Plain SMS",
)
@sms_compat_router.post("/send", response_model=SuccessMessageResponse)
async def send_plain_sms(
    body: PlainSmsRequest,
    service: Annotated[MobileAuthService, Depends(get_mobile_auth_service)],
) -> SuccessMessageResponse:
    await service.send_plain_sms(recipient=body.recipient, message=body.message)
    return SuccessMessageResponse(success=True, message="SMS sent successfully.")


# ======================== Password Management ========================


@router.post(
    "/password/reset/check-phone",
    response_model=SuccessMessageResponse,
    summary="Check Phone for Password Reset",
)
async def check_phone_for_reset(
    body: CheckPhoneRequest,
    service: Annotated[MobileAuthService, Depends(get_mobile_auth_service)],
) -> SuccessMessageResponse:
    user = await service.auth_repo.get_by_phone(body.phone)
    if not user:
        raise EntityNotFoundError("User", body.phone)
    return SuccessMessageResponse(success=True, message="Phone number is registered.")


@router.post(
    "/password/reset/phone",
    response_model=SuccessMessageResponse,
    summary="Reset Password with Phone OTP",
)
async def reset_password_by_phone(
    body: PhoneResetPasswordRequest,
    service: Annotated[MobileAuthService, Depends(get_mobile_auth_service)],
) -> SuccessMessageResponse:
    await service.reset_password_by_phone(
        phone=body.phone,
        code=body.code,
        new_password=body.new_password,
        verification_id=body.verification_id,
    )
    return SuccessMessageResponse(success=True, message="Password reset successfully.")


@router.post(
    "/password/change",
    response_model=SuccessMessageResponse,
    summary="Change Password",
)
async def change_password(
    body: ChangePasswordRequest,
    ctx: RequireAuth,
    service: Annotated[MobileAuthService, Depends(get_mobile_auth_service)],
) -> SuccessMessageResponse:
    await service.change_password(
        user_id=ctx.user_id,
        old_password=body.old_password,
        new_password=body.new_password,
    )
    return SuccessMessageResponse(success=True, message="Password changed successfully.")


# ======================== Session & Account Lifecycle ========================


@router.get(
    "/me",
    response_model=AuthMeResponse,
    summary="Current session profile introspection",
)
async def auth_me(ctx: RequireAuth) -> AuthMeResponse:
    return AuthMeResponse(
        user_id=ctx.user_id,
        email=ctx.email,
        roles=list(ctx.roles),
        customer_id=ctx.customer_id,
        provider_id=ctx.provider_id,
        handyman_id=ctx.handyman_id,
    )


@router.post(
    "/session/restore",
    response_model=AuthSessionResponse,
    summary="Restore active session for authenticated user",
)
async def restore_session(
    ctx: RequireAuth,
    service: Annotated[MobileAuthService, Depends(get_mobile_auth_service)],
) -> AuthSessionResponse:
    session = await service.restore_session(ctx.user_id)
    return AuthSessionResponse(
        access_token=session.access_token,
        refresh_token=session.refresh_token,
        token_type=session.token_type,
        expires_in=session.expires_in,
        roles=session.roles,
        customer_id=session.customer_id,
        provider_id=session.provider_id,
        handyman_id=session.handyman_id,
        user=session.user,
    )


@router.post(
    "/logout",
    response_model=SuccessMessageResponse,
    summary="Sign Out / Revoke Session",
)
async def logout(
    ctx: RequireAuth,
    service: Annotated[MobileAuthService, Depends(get_mobile_auth_service)],
) -> SuccessMessageResponse:
    await service.logout(ctx.user_id)
    return SuccessMessageResponse(success=True, message="Successfully logged out.")


@router.delete(
    "/account",
    response_model=SuccessMessageResponse,
    summary="Delete Customer Account",
)
async def delete_customer_account(
    ctx: RequireCustomer,
    service: Annotated[MobileAuthService, Depends(get_mobile_auth_service)],
) -> SuccessMessageResponse:
    assert ctx.customer_id is not None
    await service.delete_customer_account(user_id=ctx.user_id, customer_id=ctx.customer_id)
    return SuccessMessageResponse(success=True, message="Account successfully deleted.")
