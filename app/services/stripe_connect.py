"""
Stripe Connect Express onboarding for students (Technical Implementation
Plan step 3.a.i, student half). A student needs a Connect account to
receive any payout at all — this module creates one and generates the
hosted onboarding link Stripe requires before that account can actually
receive a transfer.

Businesses do NOT get a Connect account (they're payers, not payees) — see
app/services/stripe_customers.py for the business-side equivalent.

Genuinely unverified against the real Stripe API, unlike most integrations
in this codebase: Stripe has no keyless or public-test-credential path (no
equivalent of hCaptcha's or HaveIBeenPwned's account-free test access), so
the real-Stripe branches below can't be exercised end-to-end without a
real Stripe account and STRIPE_SECRET_KEY — written against stripe-python
10.12.0's actual typed API (confirmed installed and importable in this
environment), that's the extent of verification possible for those
branches specifically. See app/services/stripe_dev_mode.py for the
development-only simulated path, which every endpoint calling this module
IS fully exercised through in local dev/demo and in this project's own
test suite.
"""
import logging

import stripe

from app.core.config import settings
from app.models.user import StudentProfile
from app.services.stripe_dev_mode import fake_id, is_simulated

logger = logging.getLogger("caplink.stripe_connect")


class StripeNotConfigured(RuntimeError):
    """Raised instead of silently no-op'ing — unlike CAPTCHA or the HIBP
    breach check, payment setup must fail closed in staging/production: a
    broken setup silently "succeeding" would corrupt real financial state
    that's expensive to unwind (see README's Payments section). In
    `development` with no key set, see stripe_dev_mode.py instead — this
    never gets raised there."""


def _require_stripe_configured() -> None:
    if not settings.STRIPE_SECRET_KEY:
        raise StripeNotConfigured(
            "STRIPE_SECRET_KEY is not set — Stripe Connect onboarding cannot proceed. "
            "See README's Payments section."
        )
    stripe.api_key = settings.STRIPE_SECRET_KEY


def ensure_connect_account(student: StudentProfile, email: str) -> str:
    """Creates the student's Express account on first call; returns the
    existing account id on every subsequent call. Requesting only the
    `transfers` capability (not `card_payments`) — a student never charges
    anyone, only receives transfers, so there's no reason to ask Stripe to
    underwrite more than that."""
    if student.stripe_connect_account_id:
        return student.stripe_connect_account_id

    if is_simulated():
        account_id = fake_id("acct")
        student.stripe_connect_account_id = account_id
        logger.info("stripe_connect_account_simulated", extra={"student_profile_id": student.id, "account_id": account_id})
        return account_id

    _require_stripe_configured()
    account = stripe.Account.create(
        type="express",
        country="GB",
        email=email,
        capabilities={"transfers": {"requested": True}},
        business_type="individual",
        metadata={"caplink_student_profile_id": student.id},
    )
    student.stripe_connect_account_id = account.id
    logger.info("stripe_connect_account_created", extra={"student_profile_id": student.id, "account_id": account.id})
    return account.id


def create_onboarding_link(account_id: str) -> str:
    """A single-use, short-lived hosted URL — the frontend redirects the
    student here to actually complete identity/bank-details verification.
    Both URLs point back at the same in-app screen: `refresh_url` is where
    Stripe sends the student if the link itself expired before they
    finished (they land back here and the backend just issues a new one);
    `return_url` is where they land after finishing, successfully or not —
    only a follow-up `GET /payments/connect/status` call actually confirms
    whether onboarding is complete, per Stripe's own documented pattern
    (a completed redirect does not guarantee completed onboarding)."""
    if is_simulated():
        return f"{settings.PUBLIC_APP_URL.rstrip('/')}/app/index.html#stripe-connect-return"

    _require_stripe_configured()
    base = settings.PUBLIC_APP_URL.rstrip("/")
    link = stripe.AccountLink.create(
        account=account_id,
        refresh_url=f"{base}/app/index.html#stripe-connect-refresh",
        return_url=f"{base}/app/index.html#stripe-connect-return",
        type="account_onboarding",
    )
    return link.url


def refresh_onboarding_status(student: StudentProfile) -> bool:
    """Re-checks the account with Stripe directly rather than trusting a
    redirect back to `return_url` (see create_onboarding_link's docstring
    for why that alone proves nothing). Updates and returns
    `stripe_connect_onboarded`."""
    if not student.stripe_connect_account_id:
        return False

    if is_simulated():
        # A simulated account is "onboarded" the instant it's created —
        # there's no real hosted flow to actually complete in dev.
        student.stripe_connect_onboarded = True
        return True

    _require_stripe_configured()
    account = stripe.Account.retrieve(student.stripe_connect_account_id)
    student.stripe_connect_onboarded = bool(account.charges_enabled or account.payouts_enabled) and bool(
        account.details_submitted
    )
    return student.stripe_connect_onboarded
