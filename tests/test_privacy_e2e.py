"""Technical Implementation Plan 8.a.i — GDPR self-service data export and
account deletion (Epic 7.c) through the real HTTP API. Before this file,
test_privacy.py exercised app/services/privacy.py's functions directly
against a bare db_session — real, but never through the actual
GET /privacy/export / DELETE /privacy/account routes a user would call.
"""
from app.models.enums import ProjectCategory, StudentBand

from tests.test_golden_path_e2e import _approve_agreement, _auth, _register_business, _register_student, _seed_university

STUDENT_PASSWORD = "Correct-Horse-Battery-Privacy-1"


def test_export_returns_real_account_data(client):
    university_id = _seed_university(client, slug="privacyuni", domain="privacyuni.ac.uk")
    token = _register_student(client, university_slug="privacyuni", email="export-student@privacyuni.ac.uk")

    export = client.get("/api/v1/privacy/export", headers=_auth(token))
    assert export.status_code == 200, export.text
    data = export.json()
    assert data["account"]["email"] == "export-student@privacyuni.ac.uk"
    assert data["account"]["university_id"] == university_id
    assert "student_profile" in data


def test_account_deletion_requires_correct_password_then_anonymizes(client):
    _seed_university(client, slug="delprivacyuni", domain="delprivacyuni.ac.uk")
    token = _register_student(
        client, university_slug="delprivacyuni", email="delete-student@delprivacyuni.ac.uk"
    )

    wrong_password = client.request(
        "DELETE", "/api/v1/privacy/account", headers=_auth(token), json={"current_password": "not-the-real-one"}
    )
    assert wrong_password.status_code == 400, wrong_password.text

    # A wrong-password attempt must not have touched the account at all.
    still_works = client.get("/api/v1/privacy/export", headers=_auth(token))
    assert still_works.status_code == 200

    correct = client.request(
        "DELETE", "/api/v1/privacy/account", headers=_auth(token), json={"current_password": "Correct-Horse-Battery-42"}
    )
    assert correct.status_code == 200, correct.text

    # The anonymized account can no longer log in with its real original credentials.
    login_after = client.post(
        "/api/v1/auth/login",
        json={"email": "delete-student@delprivacyuni.ac.uk", "password": "Correct-Horse-Battery-42"},
    )
    assert login_after.status_code in (401, 403), login_after.text


def test_account_deletion_of_a_business_does_not_delete_the_contract_it_was_party_to(client):
    """The real design decision this endpoint centres on: a contract/
    milestone the deleted user was party to still legitimately belongs to
    the other party's own record, so it must survive the deletion untouched.
    """
    university_id = _seed_university(client, slug="delcontractuni", domain="delcontractuni.ac.uk")
    business_token = _register_business(client, email="del-business@example.com")
    _approve_agreement(
        client,
        business_user_email="del-business@example.com",
        university_id=university_id,
        bands=[StudentBand.YEAR_3.value],
        categories=[ProjectCategory.SOFTWARE_ENGINEERING.value],
    )
    student_token = _register_student(
        client, university_slug="delcontractuni", email="del-student@delcontractuni.ac.uk"
    )
    project = client.post(
        "/api/v1/projects",
        headers=_auth(business_token),
        json={
            "title": "Survives deletion",
            "description": "Checks a contract outlives the deleted party's account.",
            "category": ProjectCategory.SOFTWARE_ENGINEERING.value,
            "required_skills": ["Python"],
            "duration_label": "1 week",
            "hourly_rate_gbp": 20,
            "target_university_ids": [university_id],
            "target_bands": [StudentBand.YEAR_3.value],
        },
    ).json()
    application = client.post(
        "/api/v1/applications", headers=_auth(student_token), json={"project_id": project["id"]}
    ).json()
    client.post("/api/v1/payments/connect/onboarding-link", headers=_auth(student_token))
    client.post("/api/v1/payments/setup-intent", headers=_auth(business_token))
    contract = client.post(
        "/api/v1/contracts",
        headers=_auth(business_token),
        json={"application_id": application["id"], "milestones": [{"description": "Work", "payment_amount_gbp": 40}]},
    ).json()

    delete_resp = client.request(
        "DELETE",
        "/api/v1/privacy/account",
        headers=_auth(student_token),
        json={"current_password": "Correct-Horse-Battery-42"},
    )
    assert delete_resp.status_code == 200, delete_resp.text

    # The business can still see and act on the same contract afterward.
    still_visible = client.get("/api/v1/contracts/mine", headers=_auth(business_token))
    assert still_visible.status_code == 200
    assert any(c["id"] == contract["id"] for c in still_visible.json())
