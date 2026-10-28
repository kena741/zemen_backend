from pydantic import Field

from app.api.v1.schemas.common import APIModel


class FcmTokenBody(APIModel):
    fcm_token: str = Field(alias="fcmToken", min_length=1)
