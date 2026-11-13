"""Firebase Cloud Messaging (FCM) push notification service."""

from __future__ import annotations

import json
import logging
from typing import Any

import firebase_admin
from firebase_admin import credentials, messaging

from app.config import settings

logger = logging.getLogger(__name__)

_firebase_app: firebase_admin.App | None = None


def get_firebase_app() -> firebase_admin.App | None:
    """Initialize or retrieve the Firebase Admin application instance."""
    global _firebase_app
    if _firebase_app is not None:
        return _firebase_app

    if firebase_admin._apps:
        _firebase_app = firebase_admin.get_app()
        return _firebase_app

    cred = None
    if settings.FIREBASE_CREDENTIALS_JSON:
        cred_dict = json.loads(settings.FIREBASE_CREDENTIALS_JSON)
        cred = credentials.Certificate(cred_dict)
    elif settings.FIREBASE_CREDENTIALS_FILE:
        cred = credentials.Certificate(settings.FIREBASE_CREDENTIALS_FILE)

    if cred is not None:
        _firebase_app = firebase_admin.initialize_app(cred)
        logger.info("Firebase Admin initialized successfully.")
    else:
        logger.warning(
            "Firebase credentials not configured. FCM push notifications will run in dry-run/mock mode."
        )

    return _firebase_app


def send_fcm_notification(
    token: str,
    title: str,
    body: str,
    data: dict[str, str] | None = None,
) -> str | None:
    """Send an FCM push notification to a single device token.

    Returns:
        FCM message ID string if sent, or None if skipped/failed.
    """
    if not token or not token.strip():
        return None

    app = get_firebase_app()
    if app is None:
        logger.info(
            "FCM [MOCK] - To: %s... | Title: %s | Body: %s",
            token[:10],
            title,
            body,
        )
        return "mock-fcm-id"

    message = messaging.Message(
        notification=messaging.Notification(title=title, body=body),
        data=data or {},
        token=token,
    )

    try:
        response = messaging.send(message, app=app)
        return response
    except Exception as exc:
        logger.error("Failed to send FCM push notification to token %s...: %s", token[:10], exc)
        return None


def send_multicast_fcm_notification(
    tokens: list[str],
    title: str,
    body: str,
    data: dict[str, str] | None = None,
) -> int:
    """Send an FCM push notification to multiple device tokens.

    Returns:
        Number of successfully delivered messages.
    """
    valid_tokens = [t for t in tokens if t and t.strip()]
    if not valid_tokens:
        return 0

    app = get_firebase_app()
    if app is None:
        logger.info(
            "FCM [MOCK MULTICAST] - To: %d devices | Title: %s",
            len(valid_tokens),
            title,
        )
        return len(valid_tokens)

    message = messaging.MulticastMessage(
        notification=messaging.Notification(title=title, body=body),
        data=data or {},
        tokens=valid_tokens,
    )

    try:
        batch_response = messaging.send_each_for_multicast(message, app=app)
        return batch_response.success_count
    except Exception as exc:
        logger.error("Failed to send multicast FCM notification: %s", exc)
        return 0


class FCMService:
    """Wrapper class for FCM push notifications supporting test injection."""

    async def send_to_token(
        self,
        token: str,
        title: str,
        body: str,
        data: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        str_data = {str(k): str(v) for k, v in (data or {}).items()}
        msg_id = send_fcm_notification(token=token, title=title, body=body, data=str_data)
        return {"sent": msg_id is not None, "message_id": msg_id}

    async def send_multicast(
        self,
        tokens: list[str],
        title: str,
        body: str,
        data: dict[str, Any] | None = None,
    ) -> int:
        str_data = {str(k): str(v) for k, v in (data or {}).items()}
        return send_multicast_fcm_notification(tokens=tokens, title=title, body=body, data=str_data)


_fcm_service_instance: FCMService | None = None


def get_fcm_service() -> FCMService:
    global _fcm_service_instance
    if _fcm_service_instance is None:
        _fcm_service_instance = FCMService()
    return _fcm_service_instance

