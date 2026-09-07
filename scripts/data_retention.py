"""
Automated data-retention job (Technical Implementation Plan 7.a.i).
Enforces the policy documented in README's "Data protection & privacy
engineering" section — this script and that doc must be kept in sync;
the doc is the actual policy, this is just its enforcement.

Three rules, in order of how much data they touch:

1. Unverified accounts older than UNVERIFIED_ACCOUNT_RETENTION_DAYS
   (default 30) are hard-deleted outright — they hold essentially no
   activity (no profile use, no contracts are possible pre-verification),
   so there's nothing legitimate for another party to have an ongoing
   interest in keeping.
2. Accounts inactive for INACTIVE_ACCOUNT_RETENTION_DAYS (default 730,
   ~24 months) are anonymized via the same app/services/privacy.py
   function self-service deletion uses — not hard-deleted, for the exact
   reason documented there (other parties' contracts/ratings/messages).
3. RecommendationLog rows older than RECOMMENDATION_LOG_RETENTION_DAYS
   (default 365) are hard-deleted — pure profiling/training signal with
   no relationship to any other party's records, and the one table in
   this schema that grows unboundedly per user with no natural cap
   otherwise (flagged in the 7.a.ii PII audit — see README).

Defaults to a DRY RUN — reports what it would do without changing
anything. Pass --execute to actually apply. Not wired into a scheduler;
same "code is real, the schedule is a manual step" shape as
scripts/reconcile_payments.py — Render Cron Jobs is the natural home.

Run with:  python -m scripts.data_retention [--execute]
"""
import argparse
import logging
from datetime import datetime, timedelta

from app.db.session import SessionLocal
from app.models.recommendation import RecommendationLog
from app.models.user import User
from app.services.privacy import anonymize_user_account

logger = logging.getLogger("caplink.data_retention")

UNVERIFIED_ACCOUNT_RETENTION_DAYS = 30
INACTIVE_ACCOUNT_RETENTION_DAYS = 730
RECOMMENDATION_LOG_RETENTION_DAYS = 365


def run(execute: bool = False) -> dict:
    db = SessionLocal()
    now = datetime.utcnow()
    report = {"unverified_deleted": 0, "inactive_anonymized": 0, "recommendation_logs_deleted": 0}
    try:
        unverified_cutoff = now - timedelta(days=UNVERIFIED_ACCOUNT_RETENTION_DAYS)
        unverified = (
            db.query(User)
            .filter(User.is_email_verified.is_(False), User.created_at < unverified_cutoff, User.deleted_at.is_(None))
            .all()
        )
        report["unverified_deleted"] = len(unverified)
        for user in unverified:
            logger.info("retention_deleting_unverified_account", extra={"user_id": user.id, "created_at": user.created_at.isoformat()})
            if execute:
                db.delete(user)

        inactive_cutoff = now - timedelta(days=INACTIVE_ACCOUNT_RETENTION_DAYS)
        inactive = (
            db.query(User)
            .filter(
                User.is_email_verified.is_(True),
                User.deleted_at.is_(None),
                User.is_active.is_(True),
                # Inactive either means "never logged in, registered long
                # ago" or "logged in, but not for a very long time" — both
                # need checking since last_login_at is only set on an
                # actual login (see account_lockout.py).
                (User.last_login_at < inactive_cutoff)
                | ((User.last_login_at.is_(None)) & (User.created_at < inactive_cutoff)),
            )
            .all()
        )
        report["inactive_anonymized"] = len(inactive)
        for user in inactive:
            last_login = user.last_login_at.isoformat() if user.last_login_at else None
            logger.info(
                "retention_anonymizing_inactive_account", extra={"user_id": user.id, "last_login_at": last_login}
            )
            if execute:
                anonymize_user_account(db, user)

        log_cutoff = now - timedelta(days=RECOMMENDATION_LOG_RETENTION_DAYS)
        old_logs = db.query(RecommendationLog).filter(RecommendationLog.created_at < log_cutoff)
        report["recommendation_logs_deleted"] = old_logs.count()
        if execute:
            old_logs.delete(synchronize_session=False)

        if execute:
            db.commit()
    finally:
        db.close()

    logger.info("data_retention_run_complete", extra={**report, "executed": execute})
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--execute", action="store_true", help="Actually apply changes (default: dry run/report only)")
    args = parser.parse_args()
    result = run(execute=args.execute)
    mode = "EXECUTED" if args.execute else "DRY RUN"
    print(f"[{mode}] {result}")
