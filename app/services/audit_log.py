"""
Immutable audit trail for admin/moderation actions (Technical Implementation
Plan step 2.c.iv). CAPLink's own moderation surface today is narrower than
the plan wording's illustrative examples ("agreement approvals, rating
overrides, and account suspensions") — there is no rating-override or
account-suspension feature in this codebase at all, so this only ever
records actions that actually exist:

- a university admin's safeguarding-gate decision on a business agreement
  (the plan's own explicit example, and the single most safeguarding-
  critical write in the platform)
- a platform admin onboarding a new licensed university (tenant creation)
- a university admin's SAML SSO configuration changes (security-sensitive:
  this controls which IdP CAPLink will trust to authenticate that
  university's accounts)

Deliberately does NOT wrap every write in the API — that would make this a
generic request log (already covered, differently, by
app/core/observability.py's structured per-request logging), not a
moderation audit trail.
"""
from typing import Optional

from sqlalchemy.orm import Session

from app.models.audit_log import AuditLog


def record_audit_event(
    db: Session,
    *,
    actor_user_id: str,
    action: str,
    target_type: str,
    target_id: Optional[str] = None,
    details: Optional[dict] = None,
) -> AuditLog:
    """Adds and flushes (not commits) an AuditLog row onto the current
    transaction — callers commit alongside whatever else they're already
    committing, so the audit entry and the action it describes land
    atomically together or not at all."""
    entry = AuditLog(
        actor_user_id=actor_user_id,
        action=action,
        target_type=target_type,
        target_id=target_id,
        details=details,
    )
    db.add(entry)
    db.flush()
    return entry
