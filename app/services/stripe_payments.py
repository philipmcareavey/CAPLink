"""
Core milestone payment logic (Technical Implementation Plan 3.a.ii/3.a.iii,
3.b.i-iii) — replaces the old `stripe_payment_intent_id =
"pi_placeholder_replace_with_real_stripe_call"` line in
app/api/v1/endpoints/contracts.py with real Stripe calls.

The escrow pattern (3.b.i/3.b.ii) and the platform-fee split (3.a.iii) are
achieved by the SAME mechanism, not two separate features bolted together:
a PaymentIntent is created with `capture_method="manual"` and (for the
self-employed rail) `transfer_data`/`application_fee_amount` already set at
creation time. The card is authorized (funds held) immediately — that's
the "escrow" — and capturing it later is the single action that both takes
CAPLink's cut and transfers the remainder to the student's Connect account
in one atomic step. There is no separate "now send the money" call.

PAYE-rail milestones (3.c) deliberately do NOT use transfer_data or
application_fee_amount at all: a visa-restricted student is never paid via
a personal Stripe Connect transfer (that would make them look
self-employed for tax purposes, exactly what the PAYE rail exists to
avoid) — the full amount is captured to CAPLink's own platform balance and
handed to the umbrella/payroll provider instead (see
app/services/payroll.py). CAPLink's fee on a PAYE milestone is tracked for
internal reporting (`platform_fee_gbp` on the return value) but not
collected via Stripe on this path — see the docstring on
determine_payment_rail for why the two rails cannot share this part of the
flow.

Same "no keyless test path" caveat as stripe_connect.py/stripe_customers.py
for the real-Stripe branches — see app/services/stripe_dev_mode.py for the
development-only simulated path every function below falls back to when
no STRIPE_SECRET_KEY is set, which IS fully exercised (this project's own
test suite, and the existing zero-setup /app and /demo reference UIs).
"""
import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

import stripe

from app.core.config import settings
from app.models.contract import Milestone
from app.models.enums import MilestoneStatus, PaymentRail
from app.models.user import BusinessProfile, StudentProfile
from app.services.stripe_connect import StripeNotConfigured
from app.services.stripe_dev_mode import fake_id, is_simulated

logger = logging.getLogger("caplink.stripe_payments")


class MilestonePaymentError(RuntimeError):
    """Raised on a genuine payment failure (card declined, no payment
    method on file, Stripe API error) — callers turn this into a clear
    4xx, never a bare 500, since these are expected, user-actionable
    failures, not bugs."""


@dataclass
class AuthorizationResult:
    payment_intent_id: str
    status: str
    platform_fee_gbp: float


def _require_stripe_configured() -> None:
    if not settings.STRIPE_SECRET_KEY:
        raise StripeNotConfigured(
            "STRIPE_SECRET_KEY is not set — milestone payments cannot proceed. See README's Payments section."
        )
    stripe.api_key = settings.STRIPE_SECRET_KEY


def _to_pence(amount_gbp: float) -> int:
    return round(amount_gbp * 100)


def calculate_platform_fee_gbp(amount_gbp: float) -> float:
    return round(amount_gbp * settings.PLATFORM_FEE_PERCENT / 100, 2)


def authorize_milestone_payment(
    milestone: Milestone,
    business: BusinessProfile,
    student: StudentProfile,
    payment_rail: PaymentRail,
) -> AuthorizationResult:
    """Technical Implementation Plan 3.b.i — called once, when a milestone
    is first created (see contracts.py::create_contract), authorizing
    (holding) the full milestone amount on the business's saved card
    without capturing it. Raises MilestonePaymentError — never lets a
    Stripe exception escape directly — on any failure; callers should set
    the milestone to AUTHORIZATION_FAILED and surface a clear reason,
    never silently create a contract with an uncharged milestone."""
    if not business.stripe_customer_id or not business.stripe_default_payment_method_id:
        raise MilestonePaymentError(
            "This business has not finished payment setup yet — a saved card is required "
            "before creating a contract. See POST /payments/setup-intent."
        )
    if payment_rail == PaymentRail.SELF_EMPLOYED and not student.stripe_connect_account_id:
        raise MilestonePaymentError(
            "This student has not completed Stripe Connect onboarding yet — they cannot "
            "receive a payout. See POST /payments/connect/onboarding-link."
        )

    amount_pence = _to_pence(milestone.payment_amount_gbp)
    fee_gbp = calculate_platform_fee_gbp(milestone.payment_amount_gbp)

    if is_simulated():
        intent_id, intent_status = fake_id("pi"), "requires_capture"
        milestone.stripe_payment_intent_id = intent_id
        milestone.stripe_payment_intent_status = intent_status
        return AuthorizationResult(payment_intent_id=intent_id, status=intent_status, platform_fee_gbp=fee_gbp)

    _require_stripe_configured()
    params: dict = {
        "amount": amount_pence,
        "currency": "gbp",
        "customer": business.stripe_customer_id,
        "payment_method": business.stripe_default_payment_method_id,
        "off_session": True,
        "confirm": True,
        "capture_method": "manual",
        "metadata": {"milestone_id": milestone.id, "contract_id": milestone.contract_id},
    }
    if payment_rail == PaymentRail.SELF_EMPLOYED:
        # Destination charge — the mechanism that makes capture (below) both
        # collect CAPLink's fee and transfer the remainder to the student in
        # one step. Not used on the PAYE rail — see this module's docstring.
        params["transfer_data"] = {"destination": student.stripe_connect_account_id}
        params["application_fee_amount"] = _to_pence(fee_gbp)

    try:
        intent = stripe.PaymentIntent.create(**params)
    except stripe.CardError as exc:
        milestone.status = MilestoneStatus.AUTHORIZATION_FAILED
        raise MilestonePaymentError(f"Card declined: {exc.user_message or 'payment could not be authorized'}") from exc
    except stripe.StripeError as exc:
        milestone.status = MilestoneStatus.AUTHORIZATION_FAILED
        raise MilestonePaymentError(f"Payment authorization failed: {exc}") from exc

    milestone.stripe_payment_intent_id = intent.id
    milestone.stripe_payment_intent_status = intent.status
    return AuthorizationResult(payment_intent_id=intent.id, status=intent.status, platform_fee_gbp=fee_gbp)


def capture_milestone_payment(milestone: Milestone) -> str:
    """Technical Implementation Plan 3.b.ii — called from
    contracts.py::approve_and_pay_milestone. This is the moment funds
    actually move: CAPLink's fee is collected and the remainder transfers
    to the student's Connect account (self-employed rail) or the full
    amount lands on CAPLink's own balance pending payroll export (PAYE
    rail) — see this module's docstring."""
    if not milestone.stripe_payment_intent_id:
        raise MilestonePaymentError("This milestone was never authorized — nothing to capture.")

    if is_simulated():
        milestone.stripe_payment_intent_status = "succeeded"
        milestone.captured_at = datetime.utcnow()
        return "succeeded"

    _require_stripe_configured()
    try:
        intent = stripe.PaymentIntent.capture(milestone.stripe_payment_intent_id)
    except stripe.StripeError as exc:
        raise MilestonePaymentError(f"Payment capture failed: {exc}") from exc

    milestone.stripe_payment_intent_status = intent.status
    milestone.captured_at = datetime.utcnow()
    return intent.status


def cancel_milestone_authorization(milestone: Milestone) -> None:
    """A milestone rejected (or a contract terminated) before its payment
    was ever captured — Stripe's `cancel` releases the hold on the
    business's card outright. Distinct from a refund (below), which only
    applies to money that's already been captured."""
    if not milestone.stripe_payment_intent_id:
        return

    if is_simulated():
        milestone.stripe_payment_intent_status = "canceled"
        return

    _require_stripe_configured()
    try:
        intent = stripe.PaymentIntent.cancel(milestone.stripe_payment_intent_id)
    except stripe.StripeError as exc:
        raise MilestonePaymentError(f"Could not cancel authorization: {exc}") from exc
    milestone.stripe_payment_intent_status = intent.status


def refund_milestone_payment(milestone: Milestone, reason: Optional[str] = None) -> str:
    """Technical Implementation Plan 3.b.iii — a milestone already
    captured/paid, later disputed or found to be wrong. Refunds through the
    original PaymentIntent; Stripe automatically reverses the associated
    Connect transfer too when one exists (self-employed rail), so this one
    call is correct for both payment rails without branching."""
    if not milestone.stripe_payment_intent_id:
        raise MilestonePaymentError("This milestone has no payment to refund.")

    if is_simulated():
        milestone.stripe_payment_intent_status = "refunded"
        return fake_id("re")

    _require_stripe_configured()
    try:
        refund = stripe.Refund.create(
            payment_intent=milestone.stripe_payment_intent_id,
            reason="requested_by_customer",
            metadata={"caplink_reason": reason or "milestone_disputed", "milestone_id": milestone.id},
        )
    except stripe.StripeError as exc:
        raise MilestonePaymentError(f"Refund failed: {exc}") from exc

    milestone.stripe_payment_intent_status = "refunded"
    return refund.id
