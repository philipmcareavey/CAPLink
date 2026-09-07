"""
Nightly payment reconciliation job (Technical Implementation Plan 3.b.iv).
Compares every Milestone that has a Stripe PaymentIntent against Stripe's
own live record of that PaymentIntent, and flags any mismatch — the classic
"our database and the payment processor's ledger have quietly drifted
apart" check every real payments system needs, since captures, refunds, or
disputes can all happen (or fail) in ways a webhook is occasionally missed
for (a brief Stripe outage, a webhook endpoint that was briefly down).

Not wired into a scheduler yet — this workspace has no cron/scheduled-job
infrastructure and no way to verify one against the real Render service.
Run manually with:  python -m scripts.reconcile_payments
Render supports Cron Jobs as a separate service type on its dashboard
(a manual step, same "code is real, the schedule is a dashboard action"
shape as everything else in Workstream 1's CI/CD notes) — point one at
`python -m scripts.reconcile_payments` on whatever cadence is wanted.

Deliberately read-only: this never writes a "fix" back to Stripe or the
database on its own — a mismatch is exactly the kind of thing that needs a
human to look at once, not an automated correction that could paper over
(or worsen) a real problem.
"""
import logging

import stripe

from app.core.config import settings
from app.db.session import SessionLocal
from app.models.contract import Milestone

logger = logging.getLogger("caplink.reconcile_payments")


def run() -> list[dict]:
    if not settings.STRIPE_SECRET_KEY:
        logger.warning("reconciliation_skipped_stripe_not_configured")
        return []
    stripe.api_key = settings.STRIPE_SECRET_KEY

    db = SessionLocal()
    mismatches: list[dict] = []
    milestones: list[Milestone] = []
    try:
        milestones = db.query(Milestone).filter(Milestone.stripe_payment_intent_id.isnot(None)).all()
        for milestone in milestones:
            assert milestone.stripe_payment_intent_id is not None, "guaranteed by the isnot(None) filter above"
            try:
                intent = stripe.PaymentIntent.retrieve(milestone.stripe_payment_intent_id)
            except stripe.StripeError as exc:
                mismatches.append(
                    {
                        "milestone_id": milestone.id,
                        "issue": "could_not_retrieve_from_stripe",
                        "detail": str(exc),
                    }
                )
                continue

            if intent.status != milestone.stripe_payment_intent_status:
                mismatches.append(
                    {
                        "milestone_id": milestone.id,
                        "issue": "status_drift",
                        "caplink_status": milestone.stripe_payment_intent_status,
                        "stripe_status": intent.status,
                    }
                )
            if intent.amount != round(milestone.payment_amount_gbp * 100):
                mismatches.append(
                    {
                        "milestone_id": milestone.id,
                        "issue": "amount_mismatch",
                        "caplink_amount_pence": round(milestone.payment_amount_gbp * 100),
                        "stripe_amount_pence": intent.amount,
                    }
                )
    finally:
        db.close()

    for m in mismatches:
        logger.warning("payment_reconciliation_mismatch", extra=m)
    logger.info("payment_reconciliation_complete", extra={"checked": len(milestones), "mismatches": len(mismatches)})
    return mismatches


if __name__ == "__main__":
    run()
