"""Technical Implementation Plan 8.a.i — mobile device registration
(app/api/v1/endpoints/mobile.py) and the real (non-dev) email verification
flow (auth.py's /verify-email, /resend-verification), through the real
HTTP API. Neither had any coverage of the actual routes before this file.

Email verification auto-completes in `development` (see
auth.py::_start_email_verification's docstring) — the `client` fixture runs
under that default, so the real token-based flow only exists when
ENVIRONMENT is staging/production. Flipped in-process for the tests that
need it, same technique used in an earlier session to verify Epic 2.a.iii
(see caplink/CLAUDE.md's history) — this sidesteps Settings' own staging+
sqlite rejection, since it's set directly on the already-constructed
`settings` object rather than re-validated from environment variables.
"""
from app.core.config import settings
from app.models.enums import DevicePlatform, UniversityLicenseStatus, UniversityLicenseTier, UserRole
from app.models.university import University
from app.models.user import User

from tests.test_golden_path_e2e import _auth, _register_business, _register_student, _seed_university


def test_device_register_update_and_deregister(client):
    _seed_university(client, slug="deviceuni", domain="deviceuni.ac.uk")
    token = _register_student(client, university_slug="deviceuni", email="device-student@deviceuni.ac.uk")

    register = client.post(
        "/api/v1/mobile/devices",
        headers=_auth(token),
        json={"platform": DevicePlatform.IOS.value, "push_token": "apns-token-abc123", "app_version": "1.0.0"},
    )
    assert register.status_code == 201, register.text
    assert register.json()["status"] == "registered"

    # Re-registering the same token is idempotent — updates in place, not a duplicate.
    reregister = client.post(
        "/api/v1/mobile/devices",
        headers=_auth(token),
        json={"platform": DevicePlatform.IOS.value, "push_token": "apns-token-abc123", "app_version": "1.1.0"},
    )
    assert reregister.status_code == 201, reregister.text
    assert reregister.json()["status"] == "updated"
    assert reregister.json()["device_id"] == register.json()["device_id"]

    home = client.get("/api/v1/mobile/home", headers=_auth(token))
    assert home.status_code == 200, home.text
    assert home.json()["role"] == "student"

    deregister = client.request(
        "DELETE", "/api/v1/mobile/devices/apns-token-abc123", headers=_auth(token)
    )
    assert deregister.status_code == 204, deregister.text


def test_deregister_cannot_remove_another_users_device(client):
    _seed_university(client, slug="deviceuni2", domain="deviceuni2.ac.uk")
    owner_token = _register_student(client, university_slug="deviceuni2", email="owner@deviceuni2.ac.uk")
    other_token = _register_student(client, university_slug="deviceuni2", email="other@deviceuni2.ac.uk")

    client.post(
        "/api/v1/mobile/devices",
        headers=_auth(owner_token),
        json={"platform": DevicePlatform.ANDROID.value, "push_token": "shared-token-xyz"},
    )

    # Scoped by (push_token, user_id) — a different user's delete call must
    # silently no-op, not remove someone else's device registration.
    other_delete = client.request(
        "DELETE", "/api/v1/mobile/devices/shared-token-xyz", headers=_auth(other_token)
    )
    assert other_delete.status_code == 204

    home_still_works = client.get("/api/v1/mobile/home", headers=_auth(owner_token))
    assert home_still_works.status_code == 200


def test_mobile_home_reflects_business_role(client):
    business_token = _register_business(client, email="mobile-business@example.com")
    home = client.get("/api/v1/mobile/home", headers=_auth(business_token))
    assert home.status_code == 200, home.text
    assert home.json()["role"] == "business"
    assert "trust_tier" in home.json()


def test_resend_verification_gives_identical_response_regardless_of_account_existence(client):
    """Deliberately not testable by checking WHAT happened (no ESP is wired
    up — app/services/email.py just logs), only that a real account and a
    nonexistent one produce the exact same response, so this endpoint can
    never be used as an oracle for which emails have accounts."""
    _seed_university(client, slug="resendveruni", domain="resendveruni.ac.uk")
    _register_student(client, university_slug="resendveruni", email="real@resendveruni.ac.uk")

    real_account = client.post("/api/v1/auth/resend-verification", json={"email": "real@resendveruni.ac.uk"})
    fake_account = client.post(
        "/api/v1/auth/resend-verification", json={"email": "definitely-not-registered@resendveruni.ac.uk"}
    )
    assert real_account.status_code == 200
    assert fake_account.status_code == 200
    assert real_account.json() == fake_account.json()


def test_verify_email_real_non_dev_flow(client, monkeypatch):
    db = client.db_sessionmaker()
    try:
        db.add(
            University(
                name="Verify University",
                slug="verifyuni",
                domain="verifyuni.ac.uk",
                license_tier=UniversityLicenseTier.ENTERPRISE,
                license_status=UniversityLicenseStatus.ACTIVE,
                license_seats=10,
            )
        )
        db.commit()
    finally:
        db.close()

    # Force the real (non-auto-verifying) path for registration only.
    monkeypatch.setattr(settings, "ENVIRONMENT", "staging")
    try:
        register = client.post(
            "/api/v1/auth/register/student",
            json={
                "email": "verify-me@verifyuni.ac.uk",
                "password": "Correct-Horse-Battery-42",
                "full_name": "Verify Student",
                "university_slug": "verifyuni",
                "degree_title": "BSc Computer Science",
                "band": "year_3",
                "data_sharing_consent": True,
            },
        )
    finally:
        monkeypatch.setattr(settings, "ENVIRONMENT", "development")

    assert register.status_code == 201, register.text
    assert "access_token" not in register.json(), "staging must not auto-issue tokens the way development does"

    # Not verified yet — login must be refused.
    blocked_login = client.post(
        "/api/v1/auth/login", json={"email": "verify-me@verifyuni.ac.uk", "password": "Correct-Horse-Battery-42"}
    )
    assert blocked_login.status_code == 403, blocked_login.text

    # Grab the real token the way the (unwired) email service would have sent it.
    db = client.db_sessionmaker()
    try:
        user = db.query(User).filter(User.email == "verify-me@verifyuni.ac.uk").first()
        assert user is not None and user.role == UserRole.STUDENT
        token = user.email_verification_token
        assert token, "a real token should have been generated outside development"
    finally:
        db.close()

    bad_token = client.get("/api/v1/auth/verify-email", params={"token": "not-the-real-token"})
    assert bad_token.status_code == 400, bad_token.text

    verify = client.get("/api/v1/auth/verify-email", params={"token": token})
    assert verify.status_code == 200, verify.text

    now_logs_in = client.post(
        "/api/v1/auth/login", json={"email": "verify-me@verifyuni.ac.uk", "password": "Correct-Horse-Battery-42"}
    )
    assert now_logs_in.status_code == 200, now_logs_in.text

    # The token is single-use — it can't be replayed.
    replay = client.get("/api/v1/auth/verify-email", params={"token": token})
    assert replay.status_code == 400, replay.text
