"""
Thin notification abstraction. Mobile clients register a device token via
POST /api/v1/mobile/devices; this service fans out to the right channel.

Push delivery follows the same pattern as Sentry/hCaptcha (app/core/config.py):
FIREBASE_CREDENTIALS_JSON empty (the default everywhere, dev/staging/production
alike) means logging-only, no environment check. Once a real Firebase service
account JSON is configured, `_send_push` delivers via firebase_admin.messaging
instead. firebase-admin lives in requirements-integrations.txt, not
requirements.txt (heavy compiled dependency tree — see that file's comment),
so it's imported lazily and `is_available()` mirrors
app/services/matching/embeddings.py's is_available() pattern for the same
reason: CI's `test` job never installs it.
"""
import logging
from typing import Any, Iterable, Optional

from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.device import Device
from app.models.user import User

logger = logging.getLogger("caplink.notifications")

_firebase_app: Any = None  # cached firebase_admin.App — initialize_app() raises if called twice


def is_available() -> bool:
    """Whether firebase_admin is importable in this environment."""
    try:
        import firebase_admin  # noqa: F401
    except ImportError:
        return False
    return True


def _get_firebase_app() -> Any:
    """Lazily initializes and caches the firebase_admin App — initialize_app()
    raises ValueError if called twice with the default app name, so this must
    only ever build it once per process."""
    global _firebase_app
    if _firebase_app is None:
        import firebase_admin
        from firebase_admin import credentials

        cert = credentials.Certificate(settings.FIREBASE_CREDENTIALS_JSON)
        _firebase_app = firebase_admin.initialize_app(cert)
    return _firebase_app


def _send_push(db: Session, device: Device, title: str, body: str, data: Optional[dict] = None) -> None:
    if not settings.FIREBASE_CREDENTIALS_JSON:
        # Placeholder — logging-only until a real Firebase service account is configured.
        logger.info(
            "push_notification",
            extra={"push_token_prefix": device.push_token[:12], "title": title, "body": body, "data": data},
        )
        return

    from firebase_admin import messaging

    message = messaging.Message(
        notification=messaging.Notification(title=title, body=body),
        # FCM's data payload requires all-string values.
        data={k: str(v) for k, v in data.items()} if data else None,
        token=device.push_token,
    )
    try:
        messaging.send(message, app=_get_firebase_app())
    except messaging.UnregisteredError:
        # The token is no longer valid (app uninstalled, token rotated) —
        # deactivate it so future notify_user calls stop retrying it.
        device.is_active = False
        db.commit()
    except Exception as exc:  # noqa: BLE001 — a failed push must never break the caller's request
        logger.warning("push_send_failed", extra={"device_id": device.id, "error": str(exc)})


def notify_user(db: Session, user_id: str, title: str, body: str, data: dict | None = None) -> None:
    devices: Iterable[Device] = (
        db.query(Device).filter(Device.user_id == user_id, Device.is_active == True).all()  # noqa: E712
    )
    for device in devices:
        _send_push(db, device, title, body, data)


NOTIFICATION_TEMPLATES = {
    "new_match": ("New project match", "We found a project that fits your profile: {title}"),
    "application_status": ("Application update", "Your application for {title} is now {status}"),
    "new_message": ("New message", "{sender_name} sent you a message"),
    "milestone_paid": ("Payment released", "£{amount} has been released for '{milestone}'"),
    "rating_released": ("New rating", "You've received a new rating — check your profile"),
    "milestone_disputed": ("Payment disputed", "A dispute has been raised on '{milestone}' — our team is reviewing it"),
}


def notify_from_template(db: Session, user_id: str, template_key: str, **kwargs) -> None:
    user = db.query(User).filter(User.id == user_id).first()
    if user is not None and template_key in user.notification_opt_outs:
        return
    title, body_template = NOTIFICATION_TEMPLATES[template_key]
    notify_user(db, user_id, title, body_template.format(**kwargs))
