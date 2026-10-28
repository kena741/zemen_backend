from fastapi import APIRouter

from app.api.v1.schemas.auth import AuthMeResponse
from app.core.security.deps import RequireAuth

router = APIRouter(prefix="/auth", tags=["Auth"])


@router.get(
    "/me",
    response_model=AuthMeResponse,
    operation_id="auth_me",
    summary="Current session profiles",
    description="Validates the Supabase access token and returns linked customer/provider/handyman ids.",
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
