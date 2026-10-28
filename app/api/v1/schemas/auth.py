from uuid import UUID

from pydantic import Field

from app.api.v1.schemas.common import APIModel


class AuthMeResponse(APIModel):
    user_id: UUID
    email: str | None = None
    roles: list[str] = Field(description="Linked Zemen roles for this auth user")
    customer_id: UUID | None = None
    provider_id: UUID | None = None
    handyman_id: UUID | None = None
