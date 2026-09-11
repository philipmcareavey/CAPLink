"""Technical Implementation Plan 8.a.i — postcode-radius local business
search (app/api/v1/endpoints/local_search.py) through the real HTTP API.
Genuinely real business logic worth exercising end-to-end, not just simple
CRUD: it's another surface the safeguarding gate applies to (only an
APPROVED agreement covering the student's own band makes a business
eligible at all), plus real radius filtering (haversine distance) and
degree-relevance scoring/sorting — none of which had any HTTP-level
coverage before this file.

University/business coordinates are seeded directly via ORM rather than
through PATCH /universities/{id}/location, which calls a real postcodes.io
geocoding API — exactly the kind of live network dependency this project's
test suite avoids unless deliberately testing that integration.
"""
from app.models.enums import AgreementStatus, ProjectCategory, StudentBand
from app.models.policy import UniversityBusinessAgreement
from app.models.university import University
from app.models.user import BusinessProfile

from tests.test_golden_path_e2e import _auth, _register_business, _register_student, _seed_university

MANCHESTER_LAT, MANCHESTER_LON = 53.4808, -2.2426
LIVERPOOL_LAT, LIVERPOOL_LON = 53.4084, -2.9916  # ~35 miles away — outside 10, inside the endpoint's 100-mile max


def _set_campus_location(client, university_id, lat, lon):
    db = client.db_sessionmaker()
    try:
        university = db.query(University).filter(University.id == university_id).first()
        university.latitude = lat
        university.longitude = lon
        university.postcode = "M13 9PL"
        db.commit()
    finally:
        db.close()


def _seed_approved_business(client, *, business_user_email, university_id, bands, categories, lat, lon):
    db = client.db_sessionmaker()
    try:
        business = (
            db.query(BusinessProfile)
            .join(BusinessProfile.user)
            .filter(BusinessProfile.user.has(email=business_user_email))
            .first()
        )
        assert business is not None
        business.latitude = lat
        business.longitude = lon
        business.postcode = "M1 1AA"
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
        return business.id
    finally:
        db.close()


def test_local_search_filters_by_radius_band_and_returns_meta(client):
    university_id = _seed_university(client, slug="localsearchuni", domain="localsearchuni.ac.uk")
    _set_campus_location(client, university_id, MANCHESTER_LAT, MANCHESTER_LON)

    _register_business(client, email="nearby-business@example.com")
    _seed_approved_business(
        client,
        business_user_email="nearby-business@example.com",
        university_id=university_id,
        bands=[StudentBand.YEAR_3.value],
        categories=[ProjectCategory.SOFTWARE_ENGINEERING.value],
        lat=MANCHESTER_LAT,
        lon=MANCHESTER_LON,
    )

    _register_business(client, email="far-business@example.com")
    _seed_approved_business(
        client,
        business_user_email="far-business@example.com",
        university_id=university_id,
        bands=[StudentBand.YEAR_3.value],
        categories=[ProjectCategory.SOFTWARE_ENGINEERING.value],
        lat=LIVERPOOL_LAT,
        lon=LIVERPOOL_LON,
    )

    # A business with no agreement covering this student's band at all —
    # the safeguarding gate must exclude it regardless of distance.
    _register_business(client, email="wrong-band-business@example.com")
    _seed_approved_business(
        client,
        business_user_email="wrong-band-business@example.com",
        university_id=university_id,
        bands=[StudentBand.FOUNDATION.value],
        categories=[ProjectCategory.SOFTWARE_ENGINEERING.value],
        lat=MANCHESTER_LAT,
        lon=MANCHESTER_LON,
    )

    student_token = _register_student(
        client, university_slug="localsearchuni", email="searcher@localsearchuni.ac.uk"
    )

    search = client.get(
        f"/api/v1/universities/{university_id}/local-businesses?radius_miles=10",
        headers=_auth(student_token),
    )
    assert search.status_code == 200, search.text
    results = search.json()
    assert len(results) == 1, "only the in-radius, correctly-banded business should appear"
    assert results[0]["company_name"]
    assert results[0]["distance_miles"] < 1

    meta = client.get(
        f"/api/v1/universities/{university_id}/local-businesses/meta?radius_miles=10",
        headers=_auth(student_token),
    )
    assert meta.status_code == 200, meta.text
    assert meta.json()["total_results"] == 1
    assert meta.json()["campus_postcode"] == "M13 9PL"

    # Widening the radius brings the far business into range too.
    wide_search = client.get(
        f"/api/v1/universities/{university_id}/local-businesses?radius_miles=100",
        headers=_auth(student_token),
    )
    assert len(wide_search.json()) == 2


def test_local_search_rejects_searching_another_universitys_campus(client):
    _seed_university(client, slug="ownlocaluni", domain="ownlocaluni.ac.uk")
    other_university_id = _seed_university(client, slug="otherlocaluni", domain="otherlocaluni.ac.uk")
    student_token = _register_student(client, university_slug="ownlocaluni", email="s@ownlocaluni.ac.uk")

    # The student belongs to ownlocaluni — searching otherlocaluni's campus
    # must be refused outright, regardless of whether that campus even has
    # a location set (the ownership check runs before the location check).
    forbidden = client.get(
        f"/api/v1/universities/{other_university_id}/local-businesses", headers=_auth(student_token)
    )
    assert forbidden.status_code == 403, forbidden.text


def test_local_search_400s_when_campus_location_not_set(client):
    university_id = _seed_university(client, slug="nolocationuni", domain="nolocationuni.ac.uk")
    student_token = _register_student(client, university_slug="nolocationuni", email="s2@nolocationuni.ac.uk")

    resp = client.get(f"/api/v1/universities/{university_id}/local-businesses", headers=_auth(student_token))
    assert resp.status_code == 400, resp.text
