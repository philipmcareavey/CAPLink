"""
Thin notification abstraction. Mobile clients register a device token via
POST /api/v1/mobile/devices; this service fans out to the right channel.

Kept provider-agnostic on purpose — swap the body of `_send_push` for a real
firebase_admin.messaging.send() call once Firebase credentials are wired up.
"""
import logging
from typing import Iterable

from sqlalchemy.orm import Session

from app.models.device import Device

logger = logging.getLogger("caplink.notifications")


def _send_push(push_token: str, title: str, body: str, data: dict | None = None) -> None:
    # Placeholder — replace with firebase_admin.messaging.send(...) in production.
    logger.info("PUSH -> token=%s title=%r body=%r data=%s", push_token[:12], title, body, data)


def notify_user(db: Session, user_id: str, title: str, body: str, data: dict | None = None) -> None:
    devices: Iterable[Device] = (
        db.query(Device).filter(Device.user_id == user_id, Device.is_active == True).all()  # noqa: E712
    )
    for device in devices:
        _send_push(device.push_token, title, body, data)


NOTIFICATION_TEMPLATES = {
    "new_match": ("New project match", "We found a project that fits your profile: {title}"),
    "application_status": ("Application update", "Your application for {title} is now {status}"),
    "new_message": ("New message", "{sender_name} sent you a message"),
    "milestone_paid": ("Payment released", "£{amount} has been released for '{milestone}'"),
    "rating_released": ("New rating", "You've received a new rating — check your profile"),
}


def notify_from_template(db: Session, user_id: str, template_key: str, **kwargs) -> None:
    title, body_template = NOTIFICATION_TEMPLATES[template_key]
    notify_user(db, user_id, title, body_template.format(**kwargs))
