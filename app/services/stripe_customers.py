"""
Stripe Customer + saved-payment-method setup for businesses (Technical
Implementation Plan step 3.a.i, business half). A business pays as an
ordinary Stripe Customer with a default payment method on file — not a
Connect account, which is only for payout recipients (see
app/services/stripe_connect.py's docstring).

A saved card is required because milestone payments are authorized
off-session, at contract-creation time (3.b.i) — there is no checkout page
open for the business to re-enter card details at that moment. Getting a
card onto file at all still needs a real client-side step (Stripe.js
collecting the card against the SetupIntent this module creates) that
doesn't exist yet — that's Workstream 5 (frontend), same "backend is real,
widget is missing" shape as CAPTCHA (2.c.iii). See README's Payments
section.
"""
import logging

import stripe

from app.core.config import settings
from app.models.user import BusinessProfile
from app.services.stripe_connect import StripeNotConfigured
from app.services.stripe_dev_mode import fake_id, is_simulated

logger = logging.getLogger("caplink.stripe_customers")


def _require_stripe_configured() -> None:
    if not settings.STRIPE_SECRET_KEY:
        raise StripeNotConfigured(
            "STRIPE_SECRET_KEY is not set — Stripe customer setup cannot proceed. "
            "See README's Payments section."
        )
    stripe.api_key = settings.STRIPE_SECRET_KEY


def ensure_customer(business: BusinessProfile, email: str) -> str:
    """Creates the business's Customer object on first call; returns the
    existing id on every subsequent call."""
    if business.stripe_customer_id:
        return business.stripe_customer_id

    if is_simulated():
        customer_id = fake_id("cus")
        business.stripe_customer_id = customer_id
        logger.info("stripe_customer_simulated", extra={"business_profile_id": business.id, "customer_id": customer_id})
        return customer_id

    _require_stripe_configured()
    customer = stripe.Customer.create(
        email=email,
        name=business.company_name,
        metadata={"caplink_business_profile_id": business.id},
    )
    business.stripe_customer_id = customer.id
    logger.info("stripe_customer_created", extra={"business_profile_id": business.id, "customer_id": customer.id})
    return customer.id


def create_setup_intent(customer_id: str) -> str:
    """Returns a SetupIntent client_secret — the frontend passes this to
    Stripe.js/Elements to actually collect and save a card. Nothing here
    can be confirmed without that client-side step; this only prepares the
    server side of it."""
    if is_simulated():
        return fake_id("seti") + "_secret"

    _require_stripe_configured()
    setup_intent = stripe.SetupIntent.create(
        customer=customer_id,
        payment_method_types=["card"],
        usage="off_session",  # explicit: this card will be charged later with no one present
    )
    assert setup_intent.client_secret is not None, "Stripe always returns a client_secret for a newly created SetupIntent"
    return setup_intent.client_secret


def record_default_payment_method(business: BusinessProfile, customer_id: str, payment_method_id: str) -> None:
    """Called once the frontend confirms a SetupIntent succeeded (webhook
    `setup_intent.succeeded`, or a direct client confirmation call — either
    way this is the one place that actually persists which card gets
    charged for this business's future milestones)."""
    if not is_simulated():
        _require_stripe_configured()
        stripe.Customer.modify(customer_id, invoice_settings={"default_payment_method": payment_method_id})
    business.stripe_default_payment_method_id = payment_method_id
