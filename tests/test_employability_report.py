"""Technical Implementation Plan 5.d.iii — the employability outcomes
report a university's careers team sees. Runs the whole golden path (post,
apply, hire, pay both milestones, mutual ratings) through the real HTTP API
exactly like test_golden_path_e2e.py, then checks the report a university
admin sees actually reflects it — the aggregation logic itself
(app/services/employability_report.py) has no dedicated unit test since
every input it reads only exists via that same real lifecycle.
"""
from app.core.security import hash_password
from app.models.enums import (
    AgreementStatus,
    ProjectCategory,
    StudentBand,
    UniversityLicenseStatus,
    UniversityLicenseTier,
    UserRole,
)
from app.models.policy import UniversityBusinessAgreement
from app.models.university import University
from app.models.user import BusinessProfile, User


def _seed_university_and_admin(client, *, slug="reportuni", domain="reportuni.ac.uk"):
    db = client.db_sessionmaker()
    try:
        university = University(
            name="Report University",
            slug=slug,
            domain=domain,
            license_tier=UniversityLicenseTier.ENTERPRISE,
            license_status=UniversityLicenseStatus.ACTIVE,
            license_seats=100,
            primary_contact_name="Careers Team",
            primary_contact_email=f"careers@{domain}",
        )
        db.add(university)
        db.flush()
        admin = User(
            email=f"admin@{domain}",
            hashed_password=hash_password("Correct-Horse-Battery-77"),
            role=UserRole.UNIVERSITY_ADMIN,
            full_name="Careers Admin",
            university_id=university.id,
            is_email_verified=True,
        )
        db.add(admin)
        db.commit()
        return university.id
    finally:
        db.close()


def _approve_agreement(client, *, business_user_email, university_id, bands, categories):
    db = client.db_sessionmaker()
    try:
        business = (
            db.query(BusinessProfile)
            .join(BusinessProfile.user)
            .filter(BusinessProfile.user.has(email=business_user_email))
            .first()
        )
        assert business is not None
        db.add(
            UniversityBusinessAgreement(
                university_id=university_id,
                business_id=business.id,
                status=AgreementStatus.APPROVED,
                allowed_bands=bands,
                allowed_categories=categories,
            )
        )
        db.commit()
    finally:
        db.close()


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def test_employability_report_reflects_a_completed_hire(client):
    university_id = _seed_university_and_admin(client)

    business_resp = client.post(
        "/api/v1/auth/register/business",
        json={
            "email": "business@example.com",
            "password": "Correct-Horse-Battery-99",
            "full_name": "Hiring Manager",
            "company_name": "Report Test Co",
        },
    )
    assert business_resp.status_code == 201, business_resp.text
    business_token = business_resp.json()["access_token"]
    _approve_agreement(
        client,
        business_user_email="business@example.com",
        university_id=university_id,
        bands=[StudentBand.YEAR_3.value],
        categories=[ProjectCategory.SOFTWARE_ENGINEERING.value],
    )

    project = client.post(
        "/api/v1/projects",
        headers=_auth(business_token),
        json={
            "title": "Build a landing page",
            "description": "Static marketing page.",
            "category": ProjectCategory.SOFTWARE_ENGINEERING.value,
            "required_skills": ["HTML"],
            "duration_label": "1 week",
            "hourly_rate_gbp": 20,
            "target_university_ids": [university_id],
            "target_bands": [StudentBand.YEAR_3.value],
        },
    ).json()

    student_resp = client.post(
        "/api/v1/auth/register/student",
        json={
            "email": "student@reportuni.ac.uk",
            "password": "Correct-Horse-Battery-42",
            "full_name": "Report Student",
            "university_slug": "reportuni",
            "degree_title": "BSc Computer Science",
            "band": StudentBand.YEAR_3.value,
            "data_sharing_consent": True,
        },
    )
    assert student_resp.status_code == 201, student_resp.text
    student_token = student_resp.json()["access_token"]

    application = client.post(
        "/api/v1/applications",
        headers=_auth(student_token),
        json={"project_id": project["id"], "cover_note": "Keen to help."},
    ).json()

    assert client.post("/api/v1/payments/connect/onboarding-link", headers=_auth(student_token)).status_code == 200
    assert client.post("/api/v1/payments/setup-intent", headers=_auth(business_token)).status_code == 200

    admin_login = client.post(
        "/api/v1/auth/login", json={"email": "admin@reportuni.ac.uk", "password": "Correct-Horse-Battery-77"}
    )
    assert admin_login.status_code == 200, admin_login.text
    admin_token = admin_login.json()["access_token"]

    # Before any hire, the university has one student who's applied but
    # been neither hired nor paid.
    before = client.get(f"/api/v1/universities/{university_id}/employability-report", headers=_auth(admin_token))
    assert before.status_code == 200, before.text
    before_data = before.json()
    assert before_data["total_students"] == 1
    assert before_data["applied_students"] == 1
    assert before_data["hired_students"] == 0
    assert before_data["completed_students"] == 0
    assert before_data["total_earnings_gbp"] == 0.0

    contract = client.post(
        "/api/v1/contracts",
        headers=_auth(business_token),
        json={
            "application_id": application["id"],
            "milestones": [
                {"description": "First half", "payment_amount_gbp": 50},
                {"description": "Final delivery", "payment_amount_gbp": 75},
            ],
        },
    ).json()

    # Hired, but neither milestone paid yet — completed should still be 0.
    mid = client.get(f"/api/v1/universities/{university_id}/employability-report", headers=_auth(admin_token)).json()
    assert mid["hired_students"] == 1
    assert mid["completed_students"] == 0
    assert mid["total_earnings_gbp"] == 0.0

    for milestone in contract["milestones"]:
        assert (
            client.post(f"/api/v1/contracts/milestones/{milestone['id']}/submit", headers=_auth(student_token)).status_code
            == 200
        )
        assert (
            client.post(
                f"/api/v1/contracts/milestones/{milestone['id']}/approve-and-pay", headers=_auth(business_token)
            ).status_code
            == 200
        )

    student_rating = client.post(
        "/api/v1/ratings", headers=_auth(student_token), json={"contract_id": contract["id"], "overall_score": 5}
    )
    assert student_rating.status_code == 201, student_rating.text
    business_rating = client.post(
        "/api/v1/ratings", headers=_auth(business_token), json={"contract_id": contract["id"], "overall_score": 4}
    )
    assert business_rating.status_code == 201, business_rating.text

    after = client.get(
        f"/api/v1/universities/{university_id}/employability-report", headers=_auth(admin_token)
    ).json()
    assert after["total_students"] == 1
    assert after["hired_students"] == 1
    assert after["completed_students"] == 1
    assert after["total_earnings_gbp"] == 125.0
    # Only the business's rating of the student counts toward a student
    # outcome — the student's rating of the business (ratee = the business's
    # own user) is a different report's concern, not this one's.
    assert after["average_student_rating"] == 4.0
    assert after["rated_engagements"] == 1

    band_row = next(b for b in after["band_breakdown"] if b["band"] == StudentBand.YEAR_3.value)
    assert band_row["total_students"] == 1
    assert band_row["hired_students"] == 1
    assert band_row["completed_students"] == 1
    assert band_row["earnings_gbp"] == 125.0


def test_employability_report_forbids_another_universitys_admin(client):
    university_id = _seed_university_and_admin(client, slug="unia", domain="unia.ac.uk")
    _seed_university_and_admin(client, slug="unib", domain="unib.ac.uk")

    login = client.post("/api/v1/auth/login", json={"email": "admin@unib.ac.uk", "password": "Correct-Horse-Battery-77"})
    assert login.status_code == 200, login.text
    token = login.json()["access_token"]

    resp = client.get(f"/api/v1/universities/{university_id}/employability-report", headers=_auth(token))
    assert resp.status_code == 403, resp.text
