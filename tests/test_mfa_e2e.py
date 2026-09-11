"""Technical Implementation Plan 8.a.i — TOTP MFA (Epic 2.a.iv) through the
real HTTP API. Before this file, MFA's HTTP endpoints
(setup/enable/verify/disable, and /auth/login's mfa_required branch) had
zero coverage exercising the actual routes — test_mfa.py only ever tested
the pure functions in app/services/mfa.py (secret generation, backup-code
hashing) directly, never a real request through app/api/v1/endpoints/auth.py.

MFA is admin-only per ADMIN_ROLES (auth.py) — there's no public
self-registration path to become a university_admin/platform_admin, so one
is seeded directly via ORM, same pattern as test_employability_report.py.
"""
import pyotp

from app.core.security import hash_password
from app.models.enums import UniversityLicenseStatus, UniversityLicenseTier, UserRole
from app.models.university import University
from app.models.user import User

ADMIN_PASSWORD = "Correct-Horse-Battery-MFA-1"


def _seed_admin(client, *, email="mfa-admin@mfauni.ac.uk"):
    db = client.db_sessionmaker()
    try:
        university = University(
            name="MFA University",
            slug="mfauni",
            domain="mfauni.ac.uk",
            license_tier=UniversityLicenseTier.ENTERPRISE,
            license_status=UniversityLicenseStatus.ACTIVE,
            license_seats=10,
        )
        db.add(university)
        db.flush()
        admin = User(
            email=email,
            hashed_password=hash_password(ADMIN_PASSWORD),
            role=UserRole.UNIVERSITY_ADMIN,
            full_name="MFA Admin",
            university_id=university.id,
            is_email_verified=True,
        )
        db.add(admin)
        db.commit()
        return admin.id
    finally:
        db.close()


def _login(client, email):
    return client.post("/api/v1/auth/login", json={"email": email, "password": ADMIN_PASSWORD})


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def test_mfa_full_setup_challenge_and_backup_code_cycle(client):
    email = "mfa-admin@mfauni.ac.uk"
    _seed_admin(client, email=email)

    # Before MFA is enabled, login returns real tokens directly.
    plain_login = _login(client, email)
    assert plain_login.status_code == 200, plain_login.text
    assert "access_token" in plain_login.json()
    access_token = plain_login.json()["access_token"]

    setup = client.post("/api/v1/auth/mfa/setup", headers=_auth(access_token))
    assert setup.status_code == 200, setup.text
    secret = setup.json()["secret"]
    assert setup.json()["provisioning_uri"].startswith("otpauth://")

    # Enabling with a wrong code must fail, and must not turn MFA on.
    bad_enable = client.post("/api/v1/auth/mfa/enable", headers=_auth(access_token), json={"code": "000000"})
    assert bad_enable.status_code == 400, bad_enable.text

    still_no_mfa_login = _login(client, email)
    assert "access_token" in still_no_mfa_login.json(), "a failed /mfa/enable must not have enabled MFA"

    totp = pyotp.TOTP(secret)
    enable = client.post("/api/v1/auth/mfa/enable", headers=_auth(access_token), json={"code": totp.now()})
    assert enable.status_code == 200, enable.text
    backup_codes = enable.json()["backup_codes"]
    assert len(backup_codes) == 8

    # Login now challenges instead of issuing tokens directly.
    challenged = _login(client, email)
    assert challenged.status_code == 200, challenged.text
    challenge_body = challenged.json()
    assert challenge_body.get("mfa_required") is True
    mfa_token = challenge_body["mfa_token"]
    assert "access_token" not in challenge_body

    # A wrong TOTP code at the challenge is rejected.
    wrong_verify = client.post("/api/v1/auth/mfa/verify", json={"mfa_token": mfa_token, "code": "000000"})
    assert wrong_verify.status_code == 401, wrong_verify.text

    # The correct TOTP code succeeds.
    correct_verify = client.post("/api/v1/auth/mfa/verify", json={"mfa_token": mfa_token, "code": totp.now()})
    assert correct_verify.status_code == 200, correct_verify.text
    assert "access_token" in correct_verify.json()

    # A backup code works exactly once.
    second_challenge = _login(client, email).json()
    backup_code = backup_codes[0]
    backup_verify = client.post(
        "/api/v1/auth/mfa/verify", json={"mfa_token": second_challenge["mfa_token"], "code": backup_code}
    )
    assert backup_verify.status_code == 200, backup_verify.text

    third_challenge = _login(client, email).json()
    reused_backup = client.post(
        "/api/v1/auth/mfa/verify", json={"mfa_token": third_challenge["mfa_token"], "code": backup_code}
    )
    assert reused_backup.status_code == 401, reused_backup.text

    # Disabling requires a currently-valid code, not just any authenticated request.
    new_access_token = client.post(
        "/api/v1/auth/mfa/verify", json={"mfa_token": third_challenge["mfa_token"], "code": totp.now()}
    ).json()["access_token"]

    bad_disable = client.post("/api/v1/auth/mfa/disable", headers=_auth(new_access_token), json={"code": "000000"})
    assert bad_disable.status_code == 400, bad_disable.text

    good_disable = client.post(
        "/api/v1/auth/mfa/disable", headers=_auth(new_access_token), json={"code": totp.now()}
    )
    assert good_disable.status_code == 200, good_disable.text

    # MFA is genuinely off now — login issues tokens directly again.
    final_login = _login(client, email)
    assert "access_token" in final_login.json()
