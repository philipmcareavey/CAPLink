"""Technical Implementation Plan 8.a.i — the last real gap in this pass:
business/student profile GET/PATCH (app/api/v1/endpoints/businesses.py,
students.py) had zero coverage of the actual routes. The business PATCH
path is more than plain CRUD — setting a postcode triggers a real
server-side geocode (app/services/geo.py, backed by postcodes.io) and
clearing it back to "" must clear latitude/longitude too, since that's
what makes a business stop appearing in local-search radius results.
"""
from app.models.user import BusinessProfile
from app.services import geo

from tests.test_golden_path_e2e import _auth, _register_business, _register_student, _seed_university


def test_student_profile_get_and_partial_update(client):
    _seed_university(client, slug="profileuni", domain="profileuni.ac.uk")
    token = _register_student(client, university_slug="profileuni", email="profile-student@profileuni.ac.uk")

    before = client.get("/api/v1/students/me", headers=_auth(token))
    assert before.status_code == 200, before.text
    assert before.json()["skills"] == []

    update = client.patch(
        "/api/v1/students/me",
        headers=_auth(token),
        json={"skills": ["Python", "SQL"], "hourly_rate_expectation_gbp": 25},
    )
    assert update.status_code == 200, update.text
    assert update.json()["skills"] == ["Python", "SQL"]
    assert update.json()["hourly_rate_expectation_gbp"] == 25
    # A field not included in the PATCH body must be left untouched.
    assert update.json()["degree_title"] == "BSc Computer Science"


def test_business_profile_update_geocodes_a_new_postcode_and_clears_on_empty_string(client, monkeypatch):
    business_token = _register_business(client, email="profile-business@example.com")

    monkeypatch.setattr(
        geo, "geocode_postcode", lambda postcode, timeout=5.0: geo.GeocodeResult(53.4808, -2.2426, "M1 1AE")
    )

    set_postcode = client.patch(
        "/api/v1/businesses/me", headers=_auth(business_token), json={"postcode": "m1 1ae", "industry": "Tech"}
    )
    assert set_postcode.status_code == 200, set_postcode.text
    assert set_postcode.json()["industry"] == "Tech"

    db = client.db_sessionmaker()
    try:
        profile = (
            db.query(BusinessProfile)
            .join(BusinessProfile.user)
            .filter(BusinessProfile.user.has(email="profile-business@example.com"))
            .first()
        )
        assert profile.postcode == "M1 1AE"
        assert profile.latitude == 53.4808
        assert profile.longitude == -2.2426
    finally:
        db.close()

    clear_postcode = client.patch("/api/v1/businesses/me", headers=_auth(business_token), json={"postcode": ""})
    assert clear_postcode.status_code == 200, clear_postcode.text

    db = client.db_sessionmaker()
    try:
        profile = (
            db.query(BusinessProfile)
            .join(BusinessProfile.user)
            .filter(BusinessProfile.user.has(email="profile-business@example.com"))
            .first()
        )
        assert profile.postcode is None
        assert profile.latitude is None
        assert profile.longitude is None
    finally:
        db.close()


def test_business_profile_update_rejects_an_unresolvable_postcode(client, monkeypatch):
    business_token = _register_business(client, email="badpostcode-business@example.com")
    monkeypatch.setattr(geo, "geocode_postcode", lambda postcode, timeout=5.0: None)

    resp = client.patch(
        "/api/v1/businesses/me", headers=_auth(business_token), json={"postcode": "NOT A REAL POSTCODE"}
    )
    assert resp.status_code == 400, resp.text
