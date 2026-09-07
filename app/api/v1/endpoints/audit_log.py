from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import require_platform_admin
from app.db.session import get_db
from app.models.audit_log import AuditLog
from app.schemas.audit_log import AuditLogOut

router = APIRouter(prefix="/audit-log", tags=["audit-log"])


@router.get("", response_model=list[AuditLogOut])
def list_audit_log(
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db),
    _admin=Depends(require_platform_admin),
):
    """Platform-admin-only read of the immutable moderation audit trail
    (Technical Implementation Plan step 2.c.iv) — see
    app/services/audit_log.py for exactly what gets recorded here. Newest
    first; there is deliberately no PATCH/DELETE — the trail is
    write-once."""
    return db.query(AuditLog).order_by(AuditLog.created_at.desc()).limit(limit).all()
