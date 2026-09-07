import logging

import stripe
from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import PlainTextResponse
from sqlalchemy.orm import Session

from app.api.deps import require_business, require_platform_admin, require_student
from app.core.config import settings
from app.db.session import get_db
from app.models.contract import Contract, Milestone
from app.models.enums import MilestoneStatus, PaymentRail
from app.models.user import BusinessProfile, StudentProfile, User
from app.models.webhook_event import ProcessedWebhookEvent
from app.services import payroll, stripe_connect, stripe_customers
from app.services.notifications import notify_from_template
from app.services.stripe_connect import StripeNotConfigured
from app.services.stripe_dev_mode import fake_id, is_simulated

logger = logging.getLogger("caplink.payments")

router = APIRouter(prefix="/payments", tags=["payments"])


def _get_student_profile(db: Session, user: User) -> StudentProfile:
    profile = db.query(StudentProfile).filter(StudentProfile.user_id == user.id).first()
    assert profile is not None, "require_student guarantees a StudentProfile row exists"
    return profile


def _get_business_profile(db: Session, user: User) -> BusinessProfile:
    profile = db.query(BusinessProfile).filter(BusinessProfile.user_id == user.id).first()
    assert profile is not None, "require_business guarantees a BusinessProfile row exists"
    return profile


# ---------- Student: Stripe Connect (receiving payouts) ----------


@router.post("/connect/onboarding-link")
def create_connect_onboarding_link(db: Session = Depends(get_db), user: User = Depends(require_student)):
    """Technical Implementation Plan 3.a.i (student half). Returns a
    hosted Stripe URL the frontend should redirect to — collecting
    identity/bank details is Stripe's own flow, not built here. See
    app/services/stripe_connect.py."""
    student = _get_student_profile(db, user)
    try:
        account_id = stripe_connect.ensure_connect_account(student, user.email)
        db.commit()
        link_url = stripe_connect.create_onboarding_link(account_id)
    except StripeNotConfigured as exc:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, str(exc))
    except stripe.StripeError as exc:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, f"Stripe error: {exc}")
    return {"onboarding_url": link_url}


@router.get("/connect/status")
def get_connect_status(db: Session = Depends(get_db), user: User = Depends(require_student)):
    student = _get_student_profile(db, user)
    try:
        onboarded = stripe_connect.refresh_onboarding_status(student)
        db.commit()
    except StripeNotConfigured as exc:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, str(exc))
    except stripe.StripeError as exc:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, f"Stripe error: {exc}")
    return {"onboarded": onboarded}


# ---------- Business: Stripe Customer + saved card (paying) ----------


@router.post("/setup-intent")
def create_setup_intent(db: Session = Depends(get_db), user: User = Depends(require_business)):
    """Technical Implementation Plan 3.a.i (business half). Returns a
    SetupIntent client_secret for the frontend to complete with Stripe.js
    — see app/services/stripe_customers.py's docstring for why the actual
    card-collection UI is a separate (Workstream 5) piece of work. In
    simulated dev mode (see app/services/stripe_dev_mode.py) there is no
    real card-collection step to wait for, so this marks the business
    payment-ready immediately rather than leaving local dev/demo stuck
    waiting on a confirmation that would never arrive without Stripe.js."""
    business = _get_business_profile(db, user)
    try:
        customer_id = stripe_customers.ensure_customer(business, user.email)
        client_secret = stripe_customers.create_setup_intent(customer_id)
        if is_simulated():
            stripe_customers.record_default_payment_method(business, customer_id, fake_id("pm"))
        db.commit()
    except StripeNotConfigured as exc:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, str(exc))
    except stripe.StripeError as exc:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, f"Stripe error: {exc}")
    return {"client_secret": client_secret, "customer_id": customer_id, "simulated": is_simulated()}


@router.get("/setup-status")
def get_setup_status(db: Session = Depends(get_db), user: User = Depends(require_business)):
    business = _get_business_profile(db, user)
    return {"ready": bool(business.stripe_customer_id and business.stripe_default_payment_method_id)}


# ---------- Stripe webhook ----------


@router.post("/webhook", include_in_schema=False)
async def stripe_webhook(request: Request, db: Session = Depends(get_db)):
    """Technical Implementation Plan 3.a.iv. No auth dependency — Stripe
    calls this directly and authenticity is proven by the signature, not a
    bearer token. Requires the EXACT raw request body (not the parsed
    JSON) to verify that signature; MaxBodySizeMiddleware (app/core/body_limit.py)
    passes the body through unchanged so this still works correctly behind
    it.

    Idempotent via ProcessedWebhookEvent (3.a.iv's own requirement) — Stripe
    explicitly documents that the same event can be delivered more than
    once (retries on timeout/5xx from this endpoint), so every handler
    below only ever runs once per real event id, however many times Stripe
    actually sends it."""
    if not settings.STRIPE_WEBHOOK_SECRET:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Stripe webhooks are not configured")

    payload = await request.body()
    sig_header = request.headers.get("stripe-signature", "")
    try:
        event = stripe.Webhook.construct_event(payload, sig_header, settings.STRIPE_WEBHOOK_SECRET)
    except (ValueError, stripe.SignatureVerificationError):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Invalid webhook signature")

    if db.query(ProcessedWebhookEvent).filter(ProcessedWebhookEvent.stripe_event_id == event.id).first():
        return {"status": "already_processed"}

    data_object = event.data.object
    if event.type == "payment_intent.payment_failed":
        milestone = db.query(Milestone).filter(Milestone.stripe_payment_intent_id == data_object.id).first()
        if milestone is not None:
            milestone.stripe_payment_intent_status = data_object.status
            milestone.status = MilestoneStatus.AUTHORIZATION_FAILED
    elif event.type == "charge.dispute.created":
        payment_intent_id = data_object.payment_intent
        milestone = db.query(Milestone).filter(Milestone.stripe_payment_intent_id == payment_intent_id).first()
        if milestone is not None:
            milestone.status = MilestoneStatus.DISPUTED
            contract = milestone.contract
            student_user_id = (
                db.query(StudentProfile.user_id).filter(StudentProfile.id == contract.student_id).scalar()
            )
            notify_from_template(db, student_user_id, "milestone_paid", amount=0, milestone=milestone.description)
            logger.warning(
                "stripe_dispute_created",
                extra={"milestone_id": milestone.id, "payment_intent_id": payment_intent_id},
            )
    elif event.type == "payment_intent.succeeded":
        milestone = db.query(Milestone).filter(Milestone.stripe_payment_intent_id == data_object.id).first()
        if milestone is not None:
            milestone.stripe_payment_intent_status = data_object.status

    db.add(ProcessedWebhookEvent(stripe_event_id=event.id, event_type=event.type))
    db.commit()
    return {"status": "processed"}


# ---------- Platform admin: payroll export (3.c.iv) ----------


@router.get("/payroll/export.csv", response_class=PlainTextResponse)
def export_payroll(db: Session = Depends(get_db), _admin: User = Depends(require_platform_admin)):
    """A per-pay-period export of PAYE-rail milestones that have been paid
    (captured) but not yet handed to the umbrella/payroll provider — see
    app/services/payroll.py's docstring for why this produces a generic
    CSV rather than a specific provider's format (no provider is under
    contract yet). Does NOT mark anything exported — this is a read-only
    preview; app/services/payroll.py::submit_payroll_batch is the actual
    submission path a real provider integration would call, and that's
    what sets payroll_exported_at."""
    due = (
        db.query(Milestone, Contract, StudentProfile)
        .join(Contract, Milestone.contract_id == Contract.id)
        .join(StudentProfile, Contract.student_id == StudentProfile.id)
        .filter(
            Contract.payment_rail == PaymentRail.PAYE_UMBRELLA,
            Milestone.status == MilestoneStatus.PAID,
            Milestone.payroll_exported_at.is_(None),
        )
        .all()
    )
    return payroll.export_payroll_csv([(m, c, s) for m, c, s in due])
