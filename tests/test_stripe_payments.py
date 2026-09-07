"""
Unit tests for app/services/stripe_payments.py. Stripe has no keyless or
public-test-credential path (unlike hCaptcha/HaveIBeenPwned elsewhere in
this codebase), so nothing here can be a genuine live call — every Stripe
SDK function is monkeypatched. What IS verified for real: the exact
parameters this code sends to Stripe (destination charge + application_fee_amount
only on the self-employed rail, never on PAYE; manual capture always;
correct pence conversion), and that a Stripe-side failure is translated
into MilestonePaymentError with the milestone marked AUTHORIZATION_FAILED,
never a raw exception escaping to a caller.
"""
import types

import pytest
import stripe

from app.core import config
from app.models.contract import Contract, Milestone
from app.models.enums import MilestoneStatus, PaymentRail, StudentBand, UserRole
from app.models.university import University
from app.models.user import BusinessProfile, StudentProfile, User
from app.services import stripe_payments
from app.services.stripe_connect import StripeNotConfigured


def _make_business(db_session, with_payment_method=True):
    user = User(email="biz@example.com", hashed_password="x", role=UserRole.BUSINESS, full_name="B", is_email_verified=True)
    db_session.add(user)
    db_session.flush()
    business = BusinessProfile(
        user_id=user.id,
        company_name="Acme",
        stripe_customer_id="cus_123" if with_payment_method else None,
        stripe_default_payment_method_id="pm_123" if with_payment_method else None,
    )
    db_session.add(business)
    db_session.flush()
    return business


def _make_student(db_session, with_connect_account=True):
    university = University(name="Test Uni", slug="test-uni-stripe", domain="test-stripe.ac.uk")
    db_session.add(university)
    db_session.flush()
    user = User(
        email="s@test-stripe.ac.uk", hashed_password="x", role=UserRole.STUDENT,
        full_name="S", is_email_verified=True, university_id=university.id,
    )
    db_session.add(user)
    db_session.flush()
    student = StudentProfile(
        user_id=user.id, university_id=university.id, degree_title="CS", band=StudentBand.YEAR_2,
        stripe_connect_account_id="acct_123" if with_connect_account else None,
    )
    db_session.add(student)
    db_session.flush()
    return student


def _make_milestone(db_session, business, student, rail=PaymentRail.SELF_EMPLOYED):
    contract = Contract(project_id="p1", application_id="a1", student_id=student.id, business_id=business.id, payment_rail=rail)
    db_session.add(contract)
    db_session.flush()
    milestone = Milestone(contract_id=contract.id, description="Do the work", payment_amount_gbp=100.0)
    db_session.add(milestone)
    db_session.flush()
    return milestone


@pytest.fixture(autouse=True)
def stripe_configured(monkeypatch):
    monkeypatch.setattr(config.settings, "STRIPE_SECRET_KEY", "sk_test_fake")
    monkeypatch.setattr(config.settings, "PLATFORM_FEE_PERCENT", 10.0)


def test_authorize_self_employed_rail_uses_destination_charge_and_fee(db_session, monkeypatch):
    business = _make_business(db_session)
    student = _make_student(db_session)
    milestone = _make_milestone(db_session, business, student, rail=PaymentRail.SELF_EMPLOYED)

    captured_params = {}

    def fake_create(**params):
        captured_params.update(params)
        return types.SimpleNamespace(id="pi_1", status="requires_capture")

    monkeypatch.setattr(stripe.PaymentIntent, "create", fake_create)

    result = stripe_payments.authorize_milestone_payment(milestone, business, student, PaymentRail.SELF_EMPLOYED)

    assert result.payment_intent_id == "pi_1"
    assert result.platform_fee_gbp == 10.0  # 10% of £100
    assert captured_params["amount"] == 10000  # pence
    assert captured_params["capture_method"] == "manual"
    assert captured_params["transfer_data"] == {"destination": "acct_123"}
    assert captured_params["application_fee_amount"] == 1000  # 10% of 10000 pence
    assert milestone.stripe_payment_intent_id == "pi_1"
    assert milestone.stripe_payment_intent_status == "requires_capture"


def test_authorize_paye_rail_never_sets_transfer_data_or_fee(db_session, monkeypatch):
    business = _make_business(db_session)
    student = _make_student(db_session, with_connect_account=False)  # PAYE students need no Connect account
    milestone = _make_milestone(db_session, business, student, rail=PaymentRail.PAYE_UMBRELLA)

    captured_params = {}

    def fake_create(**params):
        captured_params.update(params)
        return types.SimpleNamespace(id="pi_2", status="requires_capture")

    monkeypatch.setattr(stripe.PaymentIntent, "create", fake_create)

    stripe_payments.authorize_milestone_payment(milestone, business, student, PaymentRail.PAYE_UMBRELLA)

    assert "transfer_data" not in captured_params
    assert "application_fee_amount" not in captured_params


def test_authorize_fails_closed_without_business_payment_method(db_session):
    business = _make_business(db_session, with_payment_method=False)
    student = _make_student(db_session)
    milestone = _make_milestone(db_session, business, student)

    with pytest.raises(stripe_payments.MilestonePaymentError, match="payment setup"):
        stripe_payments.authorize_milestone_payment(milestone, business, student, PaymentRail.SELF_EMPLOYED)


def test_authorize_fails_closed_without_student_connect_account(db_session):
    business = _make_business(db_session)
    student = _make_student(db_session, with_connect_account=False)
    milestone = _make_milestone(db_session, business, student)

    with pytest.raises(stripe_payments.MilestonePaymentError, match="Connect onboarding"):
        stripe_payments.authorize_milestone_payment(milestone, business, student, PaymentRail.SELF_EMPLOYED)


def test_authorize_raises_and_marks_milestone_on_card_decline(db_session, monkeypatch):
    business = _make_business(db_session)
    student = _make_student(db_session)
    milestone = _make_milestone(db_session, business, student)

    def fake_create(**params):
        raise stripe.CardError("Your card was declined.", param=None, code="card_declined")

    monkeypatch.setattr(stripe.PaymentIntent, "create", fake_create)

    with pytest.raises(stripe_payments.MilestonePaymentError, match="declined"):
        stripe_payments.authorize_milestone_payment(milestone, business, student, PaymentRail.SELF_EMPLOYED)
    assert milestone.status == MilestoneStatus.AUTHORIZATION_FAILED


def test_capture_updates_status_and_timestamp(db_session, monkeypatch):
    business = _make_business(db_session)
    student = _make_student(db_session)
    milestone = _make_milestone(db_session, business, student)
    milestone.stripe_payment_intent_id = "pi_1"

    monkeypatch.setattr(
        stripe.PaymentIntent, "capture", lambda pi_id, **kw: types.SimpleNamespace(id=pi_id, status="succeeded")
    )

    status = stripe_payments.capture_milestone_payment(milestone)
    assert status == "succeeded"
    assert milestone.stripe_payment_intent_status == "succeeded"
    assert milestone.captured_at is not None


def test_capture_without_prior_authorization_raises(db_session):
    business = _make_business(db_session)
    student = _make_student(db_session)
    milestone = _make_milestone(db_session, business, student)

    with pytest.raises(stripe_payments.MilestonePaymentError, match="never authorized"):
        stripe_payments.capture_milestone_payment(milestone)


def test_cancel_releases_authorization_hold(db_session, monkeypatch):
    business = _make_business(db_session)
    student = _make_student(db_session)
    milestone = _make_milestone(db_session, business, student)
    milestone.stripe_payment_intent_id = "pi_1"

    monkeypatch.setattr(
        stripe.PaymentIntent, "cancel", lambda pi_id, **kw: types.SimpleNamespace(id=pi_id, status="canceled")
    )

    stripe_payments.cancel_milestone_authorization(milestone)
    assert milestone.stripe_payment_intent_status == "canceled"


def test_cancel_with_no_payment_intent_is_a_safe_no_op(db_session):
    business = _make_business(db_session)
    student = _make_student(db_session)
    milestone = _make_milestone(db_session, business, student)
    stripe_payments.cancel_milestone_authorization(milestone)  # must not raise


def test_refund_calls_stripe_and_marks_milestone(db_session, monkeypatch):
    business = _make_business(db_session)
    student = _make_student(db_session)
    milestone = _make_milestone(db_session, business, student)
    milestone.stripe_payment_intent_id = "pi_1"

    monkeypatch.setattr(
        stripe.Refund, "create", lambda **kw: types.SimpleNamespace(id="re_1")
    )

    refund_id = stripe_payments.refund_milestone_payment(milestone, reason="test")
    assert refund_id == "re_1"
    assert milestone.stripe_payment_intent_status == "refunded"


def test_fails_closed_when_stripe_not_configured_outside_development(db_session, monkeypatch):
    """Unconfigured + development would simulate instead (see
    test_dev_mode_simulates_when_unconfigured below) — staging/production
    must never do that, since a "successful" simulated payment there would
    be a real, expensive lie."""
    monkeypatch.setattr(config.settings, "STRIPE_SECRET_KEY", "")
    monkeypatch.setattr(config.settings, "ENVIRONMENT", "staging")
    business = _make_business(db_session)
    student = _make_student(db_session)
    milestone = _make_milestone(db_session, business, student)

    with pytest.raises(StripeNotConfigured):
        stripe_payments.authorize_milestone_payment(milestone, business, student, PaymentRail.SELF_EMPLOYED)


def test_dev_mode_simulates_full_lifecycle_when_unconfigured(db_session, monkeypatch):
    """The critical zero-friction-dev guarantee: with no STRIPE_SECRET_KEY
    and ENVIRONMENT=development (the actual default for every local dev/demo
    run), authorize -> capture -> refund all succeed without ever calling
    the real Stripe SDK — see app/services/stripe_dev_mode.py."""
    monkeypatch.setattr(config.settings, "STRIPE_SECRET_KEY", "")
    monkeypatch.setattr(config.settings, "ENVIRONMENT", "development")

    def _boom(*args, **kwargs):
        raise AssertionError("real Stripe SDK must never be called in simulated dev mode")

    monkeypatch.setattr(stripe.PaymentIntent, "create", _boom)
    monkeypatch.setattr(stripe.PaymentIntent, "capture", _boom)
    monkeypatch.setattr(stripe.Refund, "create", _boom)

    business = _make_business(db_session)
    student = _make_student(db_session)
    milestone = _make_milestone(db_session, business, student)

    result = stripe_payments.authorize_milestone_payment(milestone, business, student, PaymentRail.SELF_EMPLOYED)
    assert result.status == "requires_capture"
    assert stripe_payments.capture_milestone_payment(milestone) == "succeeded"
    assert stripe_payments.refund_milestone_payment(milestone).startswith("re_dev_")
    assert milestone.stripe_payment_intent_status == "refunded"
