from typing import Optional

from sqlalchemy import ForeignKey, JSON, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base_class import Base, TimestampMixin, UUIDPrimaryKeyMixin


class AuditLog(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Immutable trail of admin/moderation actions (Technical Implementation
    Plan step 2.c.iv) — safeguarding-gate agreement decisions and
    university/SSO configuration changes today; see
    app/services/audit_log.py for exactly which actions record here and why.
    Rows are only ever inserted, never updated or deleted, by anything in
    this codebase — there's deliberately no PATCH/DELETE route for this
    table."""
    __tablename__ = "audit_logs"

    actor_user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False)
    action: Mapped[str] = mapped_column(String(100), nullable=False)
    target_type: Mapped[str] = mapped_column(String(100), nullable=False)
    target_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    # Small, action-specific context (e.g. an agreement decision's new
    # status/bands) — never secrets/credentials, since this table is
    # readable by platform admins as a plain audit trail.
    details: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
