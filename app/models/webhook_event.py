from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base_class import Base, TimestampMixin, UUIDPrimaryKeyMixin


class ProcessedWebhookEvent(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Technical Implementation Plan 3.a.iv — idempotency record for Stripe
    webhook events. Stripe explicitly documents that the same event can be
    delivered more than once (retries on timeout/5xx); `stripe_event_id` is
    unique per real-world event (Stripe generates it, not us), so inserting
    one here before acting on an event — and checking for a pre-existing row
    first — is what stops a retried webhook from double-capturing a payment
    or double-crediting a milestone. See app/api/v1/endpoints/payments.py's
    webhook handler."""
    __tablename__ = "processed_webhook_events"

    stripe_event_id: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    event_type: Mapped[str] = mapped_column(String(100), nullable=False)
