"""Technical Implementation Plan 3.c.iv — closes the real gap flagged in
the tracker's own notes: GET /payments/payroll/export.csv was always a
read-only preview (its own docstring says so explicitly), and
app/services/payroll.py::submit_payroll_batch — the actual submission
step that marks milestones exported — existed and was unit-tested
(tests/test_payroll.py) but was never reachable through the API at all.
POST /payments/payroll/submit closes that; this is its HTTP-level
coverage, through a real PAYE-rail milestone paid end-to-end.
"""
from app.core.security import hash_password
from app.models.enums import ProjectCategory, StudentBand, UserRole
from app.models.user import StudentProfile, User

from tests.test_golden_path_e2e import (
    _approve_agreement,
    _auth,
    _create_single_milestone_contract,
    _post_project_and_apply,
    _register_business,
    _register_student,
    _seed_university,
)


def _make_platform_admin_token(client, *, email="payroll-admin@caplink.internal", password="Correct-Horse-Battery-Pay-1"):
    db = client.db_sessionmaker()
    try:
        db.add(
            User(
                email=email,
                hashed_password=hash_password(password),
                role=UserRole.PLATFORM_ADMIN,
                full_name="Payroll Admin",
                is_email_verified=True,
            )
        )
        db.commit()
    finally:
        db.close()
    login = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert login.status_code == 200, login.text
    return login.json()["access_token"]


def _mark_visa_restricted(client, *, student_email) -> None:
    db = client.db_sessionmaker()
    try:
        student = (
            db.query(StudentProfile)
            .join(StudentProfile.user)
            .filter(User.email == student_email)
            .first()
        )
        assert student is not None
        student.visa_weekly_hour_cap = 20
        db.commit()
    finally:
        db.close()


def test_payroll_submit_marks_paid_paye_milestones_exported_and_is_idempotent(client):
    university_id = _seed_university(client, slug="payrolluni", domain="payrolluni.ac.uk")
    business_token = _register_business(client, email="payroll-business@example.com")
    _approve_agreement(
        client,
        business_user_email="payroll-business@example.com",
        university_id=university_id,
        bands=[StudentBand.YEAR_3.value],
        categories=[ProjectCategory.SOFTWARE_ENGINEERING.value],
    )
    student_email = "payroll-student@payrolluni.ac.uk"
    student_token = _register_student(client, university_slug="payrolluni", email=student_email)
    _mark_visa_restricted(client, student_email=student_email)

    _, application = _post_project_and_apply(
        client, business_token=business_token, student_token=student_token,
        university_id=university_id, title="PAYE payroll project",
    )
    contract = _create_single_milestone_contract(
        client, business_token=business_token, student_token=student_token, application_id=application["id"], amount=90,
    )
    assert contract["payment_rail"] == "paye_umbrella"
    milestone_id = contract["milestones"][0]["id"]

    client.post(f"/api/v1/contracts/milestones/{milestone_id}/submit", headers=_auth(student_token))
    paid = client.post(f"/api/v1/contracts/milestones/{milestone_id}/approve-and-pay", headers=_auth(business_token))
    assert paid.status_code == 200 and paid.json()["status"] == "paid"

    admin_token = _make_platform_admin_token(client)

    preview = client.get("/api/v1/payments/payroll/export.csv", headers=_auth(admin_token))
    assert preview.status_code == 200, preview.text
    assert "payroll-student@payrolluni.ac.uk" in preview.text

    submit = client.post("/api/v1/payments/payroll/submit", headers=_auth(admin_token))
    assert submit.status_code == 200, submit.text
    assert submit.json() == {"submitted_count": 1}

    # A second submit run must find nothing left to export — no double-submit.
    submit_again = client.post("/api/v1/payments/payroll/submit", headers=_auth(admin_token))
    assert submit_again.status_code == 200, submit_again.text
    assert submit_again.json() == {"submitted_count": 0}

    # The preview should now be empty too, for the same reason.
    preview_after = client.get("/api/v1/payments/payroll/export.csv", headers=_auth(admin_token))
    assert "payroll-student@payrolluni.ac.uk" not in preview_after.text


def test_payroll_submit_requires_platform_admin(client):
    _seed_university(client, slug="payrollforbid", domain="payrollforbid.ac.uk")
    business_token = _register_business(client, email="payroll-forbid-business@example.com")
    forbidden = client.post("/api/v1/payments/payroll/submit", headers=_auth(business_token))
    assert forbidden.status_code == 403, forbidden.text
