"""
Technical Implementation Plan 8.a.iii — end-to-end tests for critical
journeys, run through the real app (see conftest.py's `client` fixture)
rather than by calling service functions directly. Before this file, the
entire 105-test suite was unit/service-level only — every "verified via
TestClient end-to-end" claim scattered through caplink/CLAUDE.md's history
(SSO, Stripe payments, the ownership-authorization fix, CAPTCHA) was a
one-off manual script run once during that session and then thrown away,
never a permanent regression test. This file and its siblings close that
gap for the flows that matter most.

A University and its approved business agreement have no public endpoint
at all (onboarding a university is platform-admin-only, and there's no
self-registration path to *become* a platform admin) — seeded directly via
ORM through `client.db_sessionmaker`, exactly like scripts/seed_demo_data.py
does for local dev. Everything else — registration, applications,
contracts, milestones, ratings — goes through the real HTTP API.
"""
from app.models.enums import (
    AgreementStatus,
    ProjectCategory,
    StudentBand,
    UniversityLicenseStatus,
    UniversityLicenseTier,
)
from app.models.policy import UniversityBusinessAgreement
from app.models.university import University
from app.models.user import BusinessProfile


def _seed_university(client, *, slug="testuni", domain="testuni.ac.uk") -> str:
    db = client.db_sessionmaker()
    try:
        university = University(
            name="Test University",
            slug=slug,
            domain=domain,
            license_tier=UniversityLicenseTier.ENTERPRISE,
            license_status=UniversityLicenseStatus.ACTIVE,
            license_seats=100,
            primary_contact_name="Careers Team",
            primary_contact_email=f"careers@{domain}",
        )
        db.add(university)
        db.commit()
        return university.id
    finally:
        db.close()


def _approve_agreement(client, *, business_user_email, university_id, bands, categories) -> None:
    """Grants a business_profile (already created via real registration)
    an APPROVED agreement — the safeguarding gate this whole platform
    exists around. Looked up by the business's login email since the
    registration response doesn't hand back the internal business_id."""
    db = client.db_sessionmaker()
    try:
        business = (
            db.query(BusinessProfile)
            .join(BusinessProfile.user)
            .filter(BusinessProfile.user.has(email=business_user_email))
            .first()
        )
        assert business is not None, f"no BusinessProfile found for {business_user_email}"
        agreement = UniversityBusinessAgreement(
            university_id=university_id,
            business_id=business.id,
            status=AgreementStatus.APPROVED,
            allowed_bands=bands,
            allowed_categories=categories,
        )
        db.add(agreement)
        db.commit()
    finally:
        db.close()


def _register_student(client, *, university_slug, email="student@testuni.ac.uk"):
    resp = client.post(
        "/api/v1/auth/register/student",
        json={
            "email": email,
            "password": "Correct-Horse-Battery-42",
            "full_name": "Test Student",
            "university_slug": university_slug,
            "degree_title": "BSc Computer Science",
            "band": StudentBand.YEAR_3.value,
            "data_sharing_consent": True,
        },
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["access_token"]


def _register_business(client, *, email="business@example.com"):
    resp = client.post(
        "/api/v1/auth/register/business",
        json={
            "email": email,
            "password": "Correct-Horse-Battery-99",
            "full_name": "Hiring Manager",
            "company_name": "Test Co",
        },
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["access_token"]


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def test_full_project_lifecycle_from_posting_to_paid_and_rated(client):
    """The core product loop, start to finish: a university exists with an
    approved business, the business posts a project, a student applies,
    gets hired via a milestone contract, both milestones get paid out
    through the (simulated, since no STRIPE_SECRET_KEY is set in tests —
    see stripe_payments.py) escrow flow, and both sides rate each other."""
    university_id = _seed_university(client)
    business_token = _register_business(client)
    _approve_agreement(
        client,
        business_user_email="business@example.com",
        university_id=university_id,
        bands=[StudentBand.YEAR_3.value],
        categories=[ProjectCategory.SOFTWARE_ENGINEERING.value],
    )

    # Business posts a project — only possible now that its agreement is approved.
    post_resp = client.post(
        "/api/v1/projects",
        headers=_auth(business_token),
        json={
            "title": "Build a landing page",
            "description": "Static marketing page, mobile-first.",
            "category": ProjectCategory.SOFTWARE_ENGINEERING.value,
            "required_skills": ["HTML", "CSS"],
            "duration_label": "1 week",
            "hourly_rate_gbp": 20,
            "target_university_ids": [university_id],
            "target_bands": [StudentBand.YEAR_3.value],
        },
    )
    assert post_resp.status_code == 201, post_resp.text
    project = post_resp.json()
    assert project["status"] == "open"

    # Student registers, sees the project in their feed, and applies.
    student_token = _register_student(client, university_slug="testuni")
    feed_resp = client.get("/api/v1/projects/feed", headers=_auth(student_token))
    assert feed_resp.status_code == 200, feed_resp.text
    assert any(p["id"] == project["id"] for p in feed_resp.json()), "posted project should appear in the student's feed"

    apply_resp = client.post(
        "/api/v1/applications",
        headers=_auth(student_token),
        json={"project_id": project["id"], "cover_note": "Keen to help."},
    )
    assert apply_resp.status_code == 201, apply_resp.text
    application = apply_resp.json()

    # Both sides complete the (simulated) payment setup a real contract needs.
    assert client.post("/api/v1/payments/connect/onboarding-link", headers=_auth(student_token)).status_code == 200
    assert client.post("/api/v1/payments/setup-intent", headers=_auth(business_token)).status_code == 200

    contract_resp = client.post(
        "/api/v1/contracts",
        headers=_auth(business_token),
        json={
            "application_id": application["id"],
            "milestones": [
                {"description": "First half", "payment_amount_gbp": 50},
                {"description": "Final delivery", "payment_amount_gbp": 50},
            ],
        },
    )
    assert contract_resp.status_code == 201, contract_resp.text
    contract = contract_resp.json()
    assert len(contract["milestones"]) == 2

    # Student submits, business approves & pays, for each milestone.
    for milestone in contract["milestones"]:
        submit_resp = client.post(
            f"/api/v1/contracts/milestones/{milestone['id']}/submit", headers=_auth(student_token)
        )
        assert submit_resp.status_code == 200, submit_resp.text
        assert submit_resp.json()["status"] == "submitted"

        pay_resp = client.post(
            f"/api/v1/contracts/milestones/{milestone['id']}/approve-and-pay", headers=_auth(business_token)
        )
        assert pay_resp.status_code == 200, pay_resp.text
        assert pay_resp.json()["status"] == "paid"

    # Mutual blind ratings: hidden until both sides have submitted, then released.
    student_rating_resp = client.post(
        "/api/v1/ratings",
        headers=_auth(student_token),
        json={"contract_id": contract["id"], "overall_score": 5},
    )
    assert student_rating_resp.status_code == 201, student_rating_resp.text
    assert student_rating_resp.json()["is_released"] is False, "should stay hidden until the business rates too"

    business_rating_resp = client.post(
        "/api/v1/ratings",
        headers=_auth(business_token),
        json={"contract_id": contract["id"], "overall_score": 4.5},
    )
    assert business_rating_resp.status_code == 201, business_rating_resp.text
    assert business_rating_resp.json()["is_released"] is True, "both sides have now rated — should release"


def test_safeguarding_gate_blocks_project_posting_without_an_approved_agreement(client):
    """The core differentiator: a business with no agreement at all — or
    one that doesn't cover the requested band/category — cannot reach any
    students, full stop. No agreement seeded here at all."""
    university_id = _seed_university(client, slug="gateduni", domain="gateduni.ac.uk")
    business_token = _register_business(client, email="unapproved@example.com")

    resp = client.post(
        "/api/v1/projects",
        headers=_auth(business_token),
        json={
            "title": "Should be rejected",
            "description": "No agreement exists for this business at all.",
            "category": ProjectCategory.SOFTWARE_ENGINEERING.value,
            "required_skills": ["Python"],
            "duration_label": "1 week",
            "hourly_rate_gbp": 20,
            "target_university_ids": [university_id],
            "target_bands": [StudentBand.YEAR_3.value],
        },
    )
    assert resp.status_code == 403, resp.text


def test_business_cannot_act_on_another_businesss_contract(client):
    """Regression test for the real authorization bug found and fixed
    while wiring up Workstream 3 (see contracts.py's
    _assert_is_contract_party/_assert_is_contract_business docstrings):
    before that fix, any authenticated business could approve-and-pay,
    refund, or accept terms on *any* contract, not just its own."""
    university_id = _seed_university(client, slug="ownuni", domain="ownuni.ac.uk")
    owner_token = _register_business(client, email="owner@example.com")
    _approve_agreement(
        client,
        business_user_email="owner@example.com",
        university_id=university_id,
        bands=[StudentBand.YEAR_3.value],
        categories=[ProjectCategory.SOFTWARE_ENGINEERING.value],
    )
    project = client.post(
        "/api/v1/projects",
        headers=_auth(owner_token),
        json={
            "title": "Owner's project",
            "description": "Belongs to the owner business only.",
            "category": ProjectCategory.SOFTWARE_ENGINEERING.value,
            "required_skills": ["Python"],
            "duration_label": "1 week",
            "hourly_rate_gbp": 20,
            "target_university_ids": [university_id],
            "target_bands": [StudentBand.YEAR_3.value],
        },
    ).json()

    student_token = _register_student(client, university_slug="ownuni", email="s@ownuni.ac.uk")
    application = client.post(
        "/api/v1/applications",
        headers=_auth(student_token),
        json={"project_id": project["id"]},
    ).json()

    assert client.post("/api/v1/payments/connect/onboarding-link", headers=_auth(student_token)).status_code == 200
    assert client.post("/api/v1/payments/setup-intent", headers=_auth(owner_token)).status_code == 200

    contract = client.post(
        "/api/v1/contracts",
        headers=_auth(owner_token),
        json={"application_id": application["id"], "milestones": [{"description": "Work", "payment_amount_gbp": 30}]},
    ).json()

    # A second, unrelated business must not be able to touch it.
    intruder_token = _register_business(client, email="intruder@example.com")
    assert client.post("/api/v1/payments/setup-intent", headers=_auth(intruder_token)).status_code == 200

    forbidden = client.post(f"/api/v1/contracts/{contract['id']}/accept-terms", headers=_auth(intruder_token))
    assert forbidden.status_code == 403, forbidden.text

    forbidden_pay = client.post(
        f"/api/v1/contracts/milestones/{contract['milestones'][0]['id']}/approve-and-pay",
        headers=_auth(intruder_token),
    )
    assert forbidden_pay.status_code == 403, forbidden_pay.text


def _create_single_milestone_contract(client, *, business_token, student_token, application_id, amount=60):
    assert client.post("/api/v1/payments/connect/onboarding-link", headers=_auth(student_token)).status_code == 200
    assert client.post("/api/v1/payments/setup-intent", headers=_auth(business_token)).status_code == 200
    resp = client.post(
        "/api/v1/contracts",
        headers=_auth(business_token),
        json={
            "application_id": application_id,
            "milestones": [{"description": "Only milestone", "payment_amount_gbp": amount}],
        },
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


def _post_project_and_apply(client, *, business_token, student_token, university_id, title):
    project = client.post(
        "/api/v1/projects",
        headers=_auth(business_token),
        json={
            "title": title,
            "description": "Test project for reject/refund coverage.",
            "category": ProjectCategory.SOFTWARE_ENGINEERING.value,
            "required_skills": ["Python"],
            "duration_label": "1 week",
            "hourly_rate_gbp": 20,
            "target_university_ids": [university_id],
            "target_bands": [StudentBand.YEAR_3.value],
        },
    ).json()
    application = client.post(
        "/api/v1/applications",
        headers=_auth(student_token),
        json={"project_id": project["id"]},
    ).json()
    return project, application


def test_reject_milestone_releases_authorization_without_ever_paying(client):
    """Technical Implementation Plan 3.b.iii's reject path — a business
    rejects a submitted deliverable before ever capturing payment. Also a
    regression test for a real gap found and fixed alongside this test:
    approve_and_pay_milestone had no status guard at all (unlike this
    endpoint and /refund), relying entirely on Stripe's own PaymentIntent
    state machine — which the dev-mode simulation this test runs under
    doesn't enforce. Confirms a rejected milestone can no longer be
    approved-and-paid after the fix."""
    university_id = _seed_university(client, slug="rejectuni", domain="rejectuni.ac.uk")
    business_token = _register_business(client, email="reject-business@example.com")
    _approve_agreement(
        client,
        business_user_email="reject-business@example.com",
        university_id=university_id,
        bands=[StudentBand.YEAR_3.value],
        categories=[ProjectCategory.SOFTWARE_ENGINEERING.value],
    )
    student_token = _register_student(client, university_slug="rejectuni", email="reject-student@rejectuni.ac.uk")
    _, application = _post_project_and_apply(
        client, business_token=business_token, student_token=student_token,
        university_id=university_id, title="Reject-path project",
    )
    contract = _create_single_milestone_contract(
        client, business_token=business_token, student_token=student_token, application_id=application["id"],
    )
    milestone_id = contract["milestones"][0]["id"]

    submit = client.post(f"/api/v1/contracts/milestones/{milestone_id}/submit", headers=_auth(student_token))
    assert submit.status_code == 200 and submit.json()["status"] == "submitted"

    reject = client.post(f"/api/v1/contracts/milestones/{milestone_id}/reject", headers=_auth(business_token))
    assert reject.status_code == 200, reject.text
    assert reject.json()["status"] == "rejected"

    # Rejecting an already-rejected milestone should be refused, not silently repeated.
    reject_again = client.post(f"/api/v1/contracts/milestones/{milestone_id}/reject", headers=_auth(business_token))
    assert reject_again.status_code == 400, reject_again.text

    # The real regression this test guards against: a rejected milestone
    # must never be payable afterward, even though its Stripe
    # payment_intent_id still exists from the original authorization.
    pay_after_reject = client.post(
        f"/api/v1/contracts/milestones/{milestone_id}/approve-and-pay", headers=_auth(business_token)
    )
    assert pay_after_reject.status_code == 400, pay_after_reject.text


def test_refund_reverses_a_captured_payment_and_cannot_be_repeated(client):
    """Technical Implementation Plan 3.b.iii's refund path — money already
    captured/paid being reversed. Distinct code path and distinct guard
    from reject (which only applies pre-capture)."""
    university_id = _seed_university(client, slug="refunduni", domain="refunduni.ac.uk")
    business_token = _register_business(client, email="refund-business@example.com")
    _approve_agreement(
        client,
        business_user_email="refund-business@example.com",
        university_id=university_id,
        bands=[StudentBand.YEAR_3.value],
        categories=[ProjectCategory.SOFTWARE_ENGINEERING.value],
    )
    student_token = _register_student(client, university_slug="refunduni", email="refund-student@refunduni.ac.uk")
    _, application = _post_project_and_apply(
        client, business_token=business_token, student_token=student_token,
        university_id=university_id, title="Refund-path project",
    )
    contract = _create_single_milestone_contract(
        client, business_token=business_token, student_token=student_token, application_id=application["id"],
    )
    milestone_id = contract["milestones"][0]["id"]

    # A refund attempt before any payment has been captured must be refused.
    early_refund = client.post(f"/api/v1/contracts/milestones/{milestone_id}/refund", headers=_auth(business_token))
    assert early_refund.status_code == 400, early_refund.text

    client.post(f"/api/v1/contracts/milestones/{milestone_id}/submit", headers=_auth(student_token))
    pay = client.post(f"/api/v1/contracts/milestones/{milestone_id}/approve-and-pay", headers=_auth(business_token))
    assert pay.status_code == 200 and pay.json()["status"] == "paid"

    refund = client.post(f"/api/v1/contracts/milestones/{milestone_id}/refund", headers=_auth(business_token))
    assert refund.status_code == 200, refund.text
    assert refund.json()["status"] == "refunded"

    # A second refund of an already-refunded milestone must be refused.
    refund_again = client.post(f"/api/v1/contracts/milestones/{milestone_id}/refund", headers=_auth(business_token))
    assert refund_again.status_code == 400, refund_again.text

    # And it must not be payable again either, now that the fix guards on status.
    pay_after_refund = client.post(
        f"/api/v1/contracts/milestones/{milestone_id}/approve-and-pay", headers=_auth(business_token)
    )
    assert pay_after_refund.status_code == 400, pay_after_refund.text
