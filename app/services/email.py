"""
Thin email-sending abstraction (Technical Implementation Plan step
2.a.iii), same shape and same placeholder status as
app/services/notifications.py's push abstraction: kept provider-agnostic
on purpose, currently just logs instead of calling a real ESP (SendGrid,
Postmark, SES...). Swap _send_email's body for a real provider call once
one is wired up — every caller above this function is unaffected.
"""
import logging

from app.core.config import settings

logger = logging.getLogger("caplink.email")


def _send_email(to_email: str, subject: str, body: str) -> None:
    # Placeholder — replace with a real ESP call (SendGrid/Postmark/SES) in production.
    logger.info("email", extra={"to": to_email, "subject": subject, "body": body})


def send_verification_email(to_email: str, token: str) -> None:
    verify_url = f"{settings.PUBLIC_APP_URL}/api/v1/auth/verify-email?token={token}"
    _send_email(
        to_email,
        "Verify your CAPLink email address",
        f"Click to verify your email address: {verify_url}\n\n"
        f"This link expires in {settings.EMAIL_VERIFICATION_TOKEN_EXPIRE_HOURS} hours.",
    )
