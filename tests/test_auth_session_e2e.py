"""Technical Implementation Plan 8.a.i — token refresh and password change
through the real HTTP API. Both are called by every authenticated session
(refresh especially — without it, a mobile app would force a fresh login
every 30 minutes) and had zero coverage of the actual /auth/refresh and
/auth/change-password routes before this file; nothing else in the test
suite exercises them.
"""
from tests.test_golden_path_e2e import _auth, _register_student, _seed_university

REGISTRATION_PASSWORD = "Correct-Horse-Battery-42"


def test_refresh_token_issues_a_new_working_access_token(client):
    _seed_university(client, slug="refreshuni", domain="refreshuni.ac.uk")
    register = client.post(
        "/api/v1/auth/register/student",
        json={
            "email": "refresh-student@refreshuni.ac.uk",
            "password": REGISTRATION_PASSWORD,
            "full_name": "Refresh Student",
            "university_slug": "refreshuni",
            "degree_title": "BSc Computer Science",
            "band": "year_3",
            "data_sharing_consent": True,
        },
    )
    assert register.status_code == 201, register.text
    tokens = register.json()
    refresh_token = tokens["refresh_token"]

    refreshed = client.post("/api/v1/auth/refresh", json={"refresh_token": refresh_token})
    assert refreshed.status_code == 200, refreshed.text
    new_tokens = refreshed.json()
    assert "access_token" in new_tokens and "refresh_token" in new_tokens

    # The new access token actually works against a real protected endpoint.
    me = client.get("/api/v1/students/me", headers=_auth(new_tokens["access_token"]))
    assert me.status_code == 200, me.text
    assert me.json()["degree_title"] == "BSc Computer Science"


def test_refresh_rejects_a_garbage_or_wrong_type_token(client):
    garbage = client.post("/api/v1/auth/refresh", json={"refresh_token": "not-a-real-jwt-at-all"})
    assert garbage.status_code == 401, garbage.text

    _seed_university(client, slug="refreshuni2", domain="refreshuni2.ac.uk")
    access_token = _register_student(client, university_slug="refreshuni2", email="s@refreshuni2.ac.uk")
    # An access token presented where a refresh token is expected must be rejected
    # (the endpoint checks the token's own "type" claim, not just its signature).
    wrong_type = client.post("/api/v1/auth/refresh", json={"refresh_token": access_token})
    assert wrong_type.status_code == 401, wrong_type.text


def test_change_password_requires_current_password_then_actually_changes_it(client):
    _seed_university(client, slug="changepwuni", domain="changepwuni.ac.uk")
    access_token = _register_student(
        client, university_slug="changepwuni", email="changepw-student@changepwuni.ac.uk"
    )

    wrong_current = client.post(
        "/api/v1/auth/change-password",
        headers=_auth(access_token),
        json={"current_password": "not-the-real-password", "new_password": "Xk9$mQ7!vLp2#Rw4"},
    )
    assert wrong_current.status_code == 400, wrong_current.text

    # The old password must still work — a rejected change must not have side effects.
    still_logs_in = client.post(
        "/api/v1/auth/login",
        json={"email": "changepw-student@changepwuni.ac.uk", "password": REGISTRATION_PASSWORD},
    )
    assert still_logs_in.status_code == 200, still_logs_in.text

    changed = client.post(
        "/api/v1/auth/change-password",
        headers=_auth(access_token),
        json={"current_password": REGISTRATION_PASSWORD, "new_password": "Xk9$mQ7!vLp2#Rw4"},
    )
    assert changed.status_code == 200, changed.text

    old_password_now_fails = client.post(
        "/api/v1/auth/login",
        json={"email": "changepw-student@changepwuni.ac.uk", "password": REGISTRATION_PASSWORD},
    )
    assert old_password_now_fails.status_code == 401, old_password_now_fails.text

    new_password_works = client.post(
        "/api/v1/auth/login",
        json={"email": "changepw-student@changepwuni.ac.uk", "password": "Xk9$mQ7!vLp2#Rw4"},
    )
    assert new_password_works.status_code == 200, new_password_works.text


def test_change_password_rejects_a_new_password_that_fails_policy(client):
    _seed_university(client, slug="weakpwuni", domain="weakpwuni.ac.uk")
    access_token = _register_student(client, university_slug="weakpwuni", email="weak@weakpwuni.ac.uk")

    too_weak = client.post(
        "/api/v1/auth/change-password",
        headers=_auth(access_token),
        json={"current_password": REGISTRATION_PASSWORD, "new_password": "short"},
    )
    # Pydantic's own min_length=8 catches this before the handler even runs.
    assert too_weak.status_code == 422, too_weak.text
