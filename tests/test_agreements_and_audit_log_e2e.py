"""Technical Implementation Plan 8.a.i — the safeguarding gate's actual
control-panel action (a university admin approving/rejecting a business
partnership request) plus its audit-log side effect, through the real HTTP
API. Before this file, test_golden_path_e2e.py's helper seeded an already-
APPROVED agreement directly via ORM (deliberately — there's no way to reach
"approved" any other way, since onboarding a university is platform-admin-
only with no self-registration path), which is correct for testing what
happens once access is granted but never exercised the approval decision
itself, or GET /audit-log (previously only covered at the service level by
test_audit_log.py).
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
from app.models.university import University
from app.models.user import User

from tests.test_golden_path_e2e import _auth, _register_business

ADMIN_PASSWORD = "Correct-Horse-Battery-Admin-1"
PLATFORM_ADMIN_PASSWORD = "Correct-Horse-Battery-Platform-1"


def _seed_university_admin_and_platform_admin(client, *, slug="agreeuni", domain="agreeuni.ac.uk"):
    db = client.db_sessionmaker()
    try:
        university = University(
            name="Agreement University",
            slug=slug,
            domain=domain,
            license_tier=UniversityLicenseTier.ENTERPRISE,
            license_status=UniversityLicenseStatus.ACTIVE,
            license_seats=10,
        )
        db.add(university)
        db.flush()
        admin = User(
            email=f"admin@{domain}",
            hashed_password=hash_password(ADMIN_PASSWORD),
            role=UserRole.UNIVERSITY_ADMIN,
            full_name="Careers Admin",
            university_id=university.id,
            is_email_verified=True,
        )
        platform_admin = User(
            email=f"platform-admin-{slug}@caplink.internal",
            hashed_password=hash_password(PLATFORM_ADMIN_PASSWORD),
            role=UserRole.PLATFORM_ADMIN,
            full_name="Platform Admin",
            is_email_verified=True,
        )
        db.add(admin)
        db.add(platform_admin)
        db.commit()
        return university.id
    finally:
        db.close()


def _login(client, email, password):
    resp = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert resp.status_code == 200, resp.text
    return resp.json()["access_token"]


def test_agreement_request_approve_and_audit_log_lifecycle(client):
    university_id = _seed_university_admin_and_platform_admin(client, slug="agreeuni", domain="agreeuni.ac.uk")
    business_token = _register_business(client, email="agreement-business@example.com")
    admin_token = _login(client, "admin@agreeuni.ac.uk", ADMIN_PASSWORD)
    platform_admin_token = _login(
        client, "platform-admin-agreeuni@caplink.internal", PLATFORM_ADMIN_PASSWORD
    )

    request = client.post(
        f"/api/v1/universities/{university_id}/business-agreements",
        headers=_auth(business_token),
        json={"business_id": "ignored-by-endpoint"},
    )
    assert request.status_code == 201, request.text
    agreement = request.json()
    assert agreement["status"] == AgreementStatus.PENDING.value

    # A second request while one already exists is refused, not silently duplicated.
    duplicate = client.post(
        f"/api/v1/universities/{university_id}/business-agreements",
        headers=_auth(business_token),
        json={"business_id": "irrelevant"},
    )
    assert duplicate.status_code == 409, duplicate.text

    listing = client.get(
        f"/api/v1/universities/{university_id}/business-agreements", headers=_auth(admin_token)
    )
    assert listing.status_code == 200
    assert any(a["id"] == agreement["id"] for a in listing.json())

    decide = client.patch(
        f"/api/v1/universities/{university_id}/business-agreements/{agreement['id']}",
        headers=_auth(admin_token),
        json={
            "status": AgreementStatus.APPROVED.value,
            "allowed_bands": [StudentBand.YEAR_3.value],
            "allowed_categories": [ProjectCategory.SOFTWARE_ENGINEERING.value],
        },
    )
    assert decide.status_code == 200, decide.text
    assert decide.json()["status"] == AgreementStatus.APPROVED.value
    assert decide.json()["allowed_bands"] == [StudentBand.YEAR_3.value]

    # The approved business can now actually reach this university's students.
    post_project = client.post(
        "/api/v1/projects",
        headers=_auth(business_token),
        json={
            "title": "Now permitted",
            "description": "Should succeed now that the agreement is approved.",
            "category": ProjectCategory.SOFTWARE_ENGINEERING.value,
            "required_skills": ["Python"],
            "duration_label": "1 week",
            "hourly_rate_gbp": 20,
            "target_university_ids": [university_id],
            "target_bands": [StudentBand.YEAR_3.value],
        },
    )
    assert post_project.status_code == 201, post_project.text

    # The decision left a real, readable audit trail — platform-admin only.
    audit_log = client.get("/api/v1/audit-log", headers=_auth(platform_admin_token))
    assert audit_log.status_code == 200, audit_log.text
    entries = [e for e in audit_log.json() if e["target_id"] == agreement["id"]]
    assert len(entries) == 1
    assert entries[0]["action"] == "agreement_decision"
    assert entries[0]["actor_user_id"] is not None

    # A university admin (not a platform admin) must not be able to read the audit log.
    forbidden_audit = client.get("/api/v1/audit-log", headers=_auth(admin_token))
    assert forbidden_audit.status_code == 403, forbidden_audit.text


def test_admin_cannot_decide_another_universitys_agreement(client):
    university_a = _seed_university_admin_and_platform_admin(client, slug="agreeunia", domain="agreeunia.ac.uk")
    _seed_university_admin_and_platform_admin(client, slug="agreeunib", domain="agreeunib.ac.uk")
    business_token = _register_business(client, email="cross-uni-business@example.com")

    request = client.post(
        f"/api/v1/universities/{university_a}/business-agreements",
        headers=_auth(business_token),
        json={"business_id": "irrelevant"},
    )
    assert request.status_code == 201, request.text
    agreement = request.json()

    admin_b_token = _login(client, "admin@agreeunib.ac.uk", ADMIN_PASSWORD)
    forbidden = client.patch(
        f"/api/v1/universities/{university_a}/business-agreements/{agreement['id']}",
        headers=_auth(admin_b_token),
        json={"status": AgreementStatus.APPROVED.value, "allowed_bands": [], "allowed_categories": []},
    )
    assert forbidden.status_code == 403, forbidden.text
