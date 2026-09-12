"""Technical Implementation Plan 3.d (Financial Reporting) — all three
steps, none started before this session: a business-facing spend
dashboard (3.d.i), a platform-admin revenue dashboard (3.d.ii), and
auto-generated PDF receipts on milestone payment (3.d.iii). All build on
data this project already maintains (Contract/Milestone), same "pure
aggregation" shape as the employability report (5.d.iii).
"""
from app.core.security import hash_password
from app.models.enums import ProjectCategory, StudentBand, UserRole
from app.models.user import User

from tests.test_golden_path_e2e import (
    _approve_agreement,
    _auth,
    _create_single_milestone_contract,
    _post_project_and_apply,
    _register_business,
    _register_student,
    _seed_university,
)


def _make_platform_admin_token(client, *, email="finance-admin@caplink.internal", password="Correct-Horse-Battery-Fin-1"):
    db = client.db_sessionmaker()
    try:
        db.add(
            User(
                email=email,
                hashed_password=hash_password(password),
                role=UserRole.PLATFORM_ADMIN,
                full_name="Finance Admin",
                is_email_verified=True,
            )
        )
        db.commit()
    finally:
        db.close()
    login = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert login.status_code == 200, login.text
    return login.json()["access_token"]


def test_spend_report_covers_paid_and_pending_capture_amounts_for_this_business_only(client):
    university_id = _seed_university(client, slug="spenduni", domain="spenduni.ac.uk")
    business_token = _register_business(client, email="spend-business@example.com")
    _approve_agreement(
        client,
        business_user_email="spend-business@example.com",
        university_id=university_id,
        bands=[StudentBand.YEAR_3.value],
        categories=[ProjectCategory.SOFTWARE_ENGINEERING.value],
    )
    student_token = _register_student(client, university_slug="spenduni", email="spend-student@spenduni.ac.uk")

    project, application = _post_project_and_apply(
        client, business_token=business_token, student_token=student_token,
        university_id=university_id, title="Spend report project",
    )
    contract = _create_single_milestone_contract(
        client, business_token=business_token, student_token=student_token, application_id=application["id"], amount=120,
    )
    milestone_id = contract["milestones"][0]["id"]
    client.post(f"/api/v1/contracts/milestones/{milestone_id}/submit", headers=_auth(student_token))
    client.post(f"/api/v1/contracts/milestones/{milestone_id}/approve-and-pay", headers=_auth(business_token))

    # A second project/contract that's authorized but not yet captured.
    project2, application2 = _post_project_and_apply(
        client, business_token=business_token, student_token=student_token,
        university_id=university_id, title="Spend report project two",
    )
    _create_single_milestone_contract(
        client, business_token=business_token, student_token=student_token, application_id=application2["id"], amount=40,
    )

    report = client.get("/api/v1/payments/spend-report", headers=_auth(business_token))
    assert report.status_code == 200, report.text
    data = report.json()
    assert data["total_paid_gbp"] == 120.0
    assert data["total_pending_capture_gbp"] == 40.0
    by_project_ids = {p["project_id"] for p in data["by_project"]}
    assert project["id"] in by_project_ids
    assert project2["id"] in by_project_ids
    paid_entry = next(p for p in data["by_project"] if p["project_id"] == project["id"])
    assert paid_entry["paid_gbp"] == 120.0
    pending_entry = next(p for p in data["by_project"] if p["project_id"] == project2["id"])
    assert pending_entry["pending_capture_gbp"] == 40.0

    # A different business must see none of this.
    other_token = _register_business(client, email="spend-other@example.com")
    other_report = client.get("/api/v1/payments/spend-report", headers=_auth(other_token))
    assert other_report.status_code == 200, other_report.text
    assert other_report.json()["total_paid_gbp"] == 0.0
    assert other_report.json()["by_project"] == []

    # A student must not be able to reach a business-only report.
    forbidden = client.get("/api/v1/payments/spend-report", headers=_auth(student_token))
    assert forbidden.status_code == 403, forbidden.text


def test_revenue_report_is_platform_admin_only_and_reflects_the_platform_fee(client):
    university_id = _seed_university(client, slug="revuni", domain="revuni.ac.uk")
    business_token = _register_business(client, email="rev-business@example.com")
    _approve_agreement(
        client,
        business_user_email="rev-business@example.com",
        university_id=university_id,
        bands=[StudentBand.YEAR_3.value],
        categories=[ProjectCategory.SOFTWARE_ENGINEERING.value],
    )
    student_token = _register_student(client, university_slug="revuni", email="rev-student@revuni.ac.uk")
    _, application = _post_project_and_apply(
        client, business_token=business_token, student_token=student_token,
        university_id=university_id, title="Revenue report project",
    )
    contract = _create_single_milestone_contract(
        client, business_token=business_token, student_token=student_token, application_id=application["id"], amount=100,
    )
    milestone_id = contract["milestones"][0]["id"]
    client.post(f"/api/v1/contracts/milestones/{milestone_id}/submit", headers=_auth(student_token))
    client.post(f"/api/v1/contracts/milestones/{milestone_id}/approve-and-pay", headers=_auth(business_token))

    admin_token = _make_platform_admin_token(client)
    report = client.get("/api/v1/payments/revenue-report", headers=_auth(admin_token))
    assert report.status_code == 200, report.text
    data = report.json()
    assert data["gross_payment_volume_gbp"] == 100.0
    assert data["platform_fee_revenue_gbp"] > 0
    assert data["license_revenue_gbp"] == 0.0

    forbidden = client.get("/api/v1/payments/revenue-report", headers=_auth(business_token))
    assert forbidden.status_code == 403, forbidden.text


def test_milestone_receipt_pdf_is_available_to_either_party_once_paid_and_forbidden_to_others(client):
    university_id = _seed_university(client, slug="receiptuni", domain="receiptuni.ac.uk")
    business_token = _register_business(client, email="receipt-business@example.com")
    _approve_agreement(
        client,
        business_user_email="receipt-business@example.com",
        university_id=university_id,
        bands=[StudentBand.YEAR_3.value],
        categories=[ProjectCategory.SOFTWARE_ENGINEERING.value],
    )
    student_token = _register_student(client, university_slug="receiptuni", email="receipt-student@receiptuni.ac.uk")
    _, application = _post_project_and_apply(
        client, business_token=business_token, student_token=student_token,
        university_id=university_id, title="Receipt project",
    )
    contract = _create_single_milestone_contract(
        client, business_token=business_token, student_token=student_token, application_id=application["id"], amount=75,
    )
    milestone_id = contract["milestones"][0]["id"]

    # Not paid yet — no receipt available.
    too_early = client.get(f"/api/v1/payments/milestones/{milestone_id}/receipt.pdf", headers=_auth(business_token))
    assert too_early.status_code == 400, too_early.text

    client.post(f"/api/v1/contracts/milestones/{milestone_id}/submit", headers=_auth(student_token))
    client.post(f"/api/v1/contracts/milestones/{milestone_id}/approve-and-pay", headers=_auth(business_token))

    business_receipt = client.get(f"/api/v1/payments/milestones/{milestone_id}/receipt.pdf", headers=_auth(business_token))
    assert business_receipt.status_code == 200, business_receipt.text
    assert business_receipt.headers["content-type"] == "application/pdf"
    assert business_receipt.content.startswith(b"%PDF")

    student_receipt = client.get(f"/api/v1/payments/milestones/{milestone_id}/receipt.pdf", headers=_auth(student_token))
    assert student_receipt.status_code == 200, student_receipt.text
    assert student_receipt.content.startswith(b"%PDF")

    intruder_token = _register_business(client, email="receipt-intruder@example.com")
    forbidden = client.get(f"/api/v1/payments/milestones/{milestone_id}/receipt.pdf", headers=_auth(intruder_token))
    assert forbidden.status_code == 403, forbidden.text

    missing = client.get("/api/v1/payments/milestones/does-not-exist/receipt.pdf", headers=_auth(business_token))
    assert missing.status_code == 404, missing.text
