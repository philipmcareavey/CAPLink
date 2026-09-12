"""Technical Implementation Plan 8.a.i — closes out the remaining
HTTP-untested endpoints its own tracker notes flagged as the last gap
before this step could be marked Done: GET /projects/mine, GET
/ratings/pending and /mine, GET /payments/connect/status and
/setup-status, POST /recommendations/{id}/feedback, and GET /universities
(list + public branding). All read-only listings or a single feedback
write — genuinely lower risk than the payments/auth/safeguarding-gate
surface already covered, which is exactly why they were left for last.
"""
from app.core.security import hash_password
from app.models.enums import ProjectCategory, StudentBand, UserRole
from app.models.recommendation import RecommendationLog
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


def test_projects_mine_returns_only_this_businesss_own_projects_any_status(client):
    university_id = _seed_university(client, slug="mineuni", domain="mineuni.ac.uk")
    owner_token = _register_business(client, email="mine-owner@example.com")
    _approve_agreement(
        client,
        business_user_email="mine-owner@example.com",
        university_id=university_id,
        bands=[StudentBand.YEAR_3.value],
        categories=[ProjectCategory.SOFTWARE_ENGINEERING.value],
    )
    project = client.post(
        "/api/v1/projects",
        headers=_auth(owner_token),
        json={
            "title": "Owner's own project",
            "description": "Should show up in GET /projects/mine.",
            "category": ProjectCategory.SOFTWARE_ENGINEERING.value,
            "required_skills": ["Python"],
            "duration_label": "1 week",
            "hourly_rate_gbp": 20,
            "target_university_ids": [university_id],
            "target_bands": [StudentBand.YEAR_3.value],
        },
    ).json()

    mine = client.get("/api/v1/projects/mine", headers=_auth(owner_token))
    assert mine.status_code == 200, mine.text
    assert [p["id"] for p in mine.json()] == [project["id"]]

    # A second, unrelated business must see none of it.
    other_token = _register_business(client, email="mine-other@example.com")
    other_mine = client.get("/api/v1/projects/mine", headers=_auth(other_token))
    assert other_mine.status_code == 200, other_mine.text
    assert other_mine.json() == []


def test_ratings_pending_and_mine_reflect_the_blind_until_both_sides_rating_rule(client):
    university_id = _seed_university(client, slug="ratinguni", domain="ratinguni.ac.uk")
    business_token = _register_business(client, email="rating-business@example.com")
    _approve_agreement(
        client,
        business_user_email="rating-business@example.com",
        university_id=university_id,
        bands=[StudentBand.YEAR_3.value],
        categories=[ProjectCategory.SOFTWARE_ENGINEERING.value],
    )
    student_token = _register_student(client, university_slug="ratinguni", email="rating-student@ratinguni.ac.uk")
    _, application = _post_project_and_apply(
        client, business_token=business_token, student_token=student_token,
        university_id=university_id, title="Ratings-coverage project",
    )
    contract = _create_single_milestone_contract(
        client, business_token=business_token, student_token=student_token, application_id=application["id"],
    )
    milestone_id = contract["milestones"][0]["id"]
    client.post(f"/api/v1/contracts/milestones/{milestone_id}/submit", headers=_auth(student_token))
    client.post(f"/api/v1/contracts/milestones/{milestone_id}/approve-and-pay", headers=_auth(business_token))

    student_rating = client.post(
        "/api/v1/ratings",
        headers=_auth(student_token),
        json={"contract_id": contract["id"], "overall_score": 5},
    )
    assert student_rating.status_code == 201, student_rating.text

    # Only the student has rated so far — it should show up as pending for
    # them, and their own history should already reveal the score they gave.
    pending = client.get("/api/v1/ratings/pending", headers=_auth(student_token))
    assert pending.status_code == 200, pending.text
    assert len(pending.json()) == 1

    mine_before_release = client.get("/api/v1/ratings/mine", headers=_auth(student_token))
    assert mine_before_release.status_code == 200, mine_before_release.text
    entry = mine_before_release.json()[0]
    assert entry["direction"] == "given"
    assert entry["is_released"] is False
    assert entry["overall_score"] == 5

    # The business hasn't rated yet — the incoming rating shows up in their
    # history (they're the ratee), but blind: not released, score hidden.
    business_mine_before = client.get("/api/v1/ratings/mine", headers=_auth(business_token))
    assert business_mine_before.status_code == 200, business_mine_before.text
    incoming_entry = business_mine_before.json()[0]
    assert incoming_entry["direction"] == "received"
    assert incoming_entry["is_released"] is False
    assert incoming_entry["overall_score"] is None

    business_rating = client.post(
        "/api/v1/ratings",
        headers=_auth(business_token),
        json={"contract_id": contract["id"], "overall_score": 4},
    )
    assert business_rating.status_code == 201, business_rating.text

    # Now both sides have rated — nothing pending anymore, and both
    # histories reveal the released score.
    assert client.get("/api/v1/ratings/pending", headers=_auth(student_token)).json() == []
    business_mine_after = client.get("/api/v1/ratings/mine", headers=_auth(business_token))
    assert business_mine_after.status_code == 200, business_mine_after.text
    received_entry = next(e for e in business_mine_after.json() if e["direction"] == "received")
    assert received_entry["direction"] == "received"
    assert received_entry["is_released"] is True
    assert received_entry["overall_score"] == 5


def test_payments_connect_status_and_setup_status_reflect_onboarding_progress(client):
    _seed_university(client, slug="paystatususi", domain="paystatusuni.ac.uk")
    business_token = _register_business(client, email="paystatus-business@example.com")
    student_token = _register_student(client, university_slug="paystatususi", email="paystatus-student@paystatusuni.ac.uk")

    # Before either side has started Stripe onboarding.
    connect_before = client.get("/api/v1/payments/connect/status", headers=_auth(student_token))
    assert connect_before.status_code == 200, connect_before.text
    assert connect_before.json() == {"onboarded": False}

    setup_before = client.get("/api/v1/payments/setup-status", headers=_auth(business_token))
    assert setup_before.status_code == 200, setup_before.text
    assert setup_before.json() == {"ready": False}

    # After completing the (simulated, no STRIPE_SECRET_KEY in tests) onboarding flow.
    assert client.post("/api/v1/payments/connect/onboarding-link", headers=_auth(student_token)).status_code == 200
    assert client.post("/api/v1/payments/setup-intent", headers=_auth(business_token)).status_code == 200

    connect_after = client.get("/api/v1/payments/connect/status", headers=_auth(student_token))
    assert connect_after.status_code == 200, connect_after.text
    assert connect_after.json() == {"onboarded": True}

    setup_after = client.get("/api/v1/payments/setup-status", headers=_auth(business_token))
    assert setup_after.status_code == 200, setup_after.text
    assert setup_after.json() == {"ready": True}


def test_recommendation_feedback_records_the_action_taken(client):
    _seed_university(client, slug="recuni", domain="recuni.ac.uk")
    student_token = _register_student(client, university_slug="recuni", email="rec-student@recuni.ac.uk")

    db = client.db_sessionmaker()
    try:
        student_user = db.query(User).filter(User.email == "rec-student@recuni.ac.uk").first()
        assert student_user is not None
        log = RecommendationLog(user_id=student_user.id, entity_type="project", entity_id="some-project-id", score=0.5)
        db.add(log)
        db.commit()
        log_id = log.id
    finally:
        db.close()

    resp = client.post(
        f"/api/v1/recommendations/{log_id}/feedback",
        headers=_auth(student_token),
        json={"action_taken": "applied"},
    )
    assert resp.status_code == 204, resp.text

    db = client.db_sessionmaker()
    try:
        refreshed = db.query(RecommendationLog).filter(RecommendationLog.id == log_id).first()
        assert refreshed is not None
        assert refreshed.action_taken == "applied"
    finally:
        db.close()

    missing = client.post(
        "/api/v1/recommendations/does-not-exist/feedback",
        headers=_auth(student_token),
        json={"action_taken": "dismissed"},
    )
    assert missing.status_code == 404, missing.text


def test_universities_list_is_platform_admin_only_and_public_branding_is_open(client):
    university_id = _seed_university(client, slug="listeduni", domain="listeduni.ac.uk")

    db = client.db_sessionmaker()
    try:
        platform_admin = User(
            email="platform-admin@caplink.internal",
            hashed_password=hash_password("Correct-Horse-Battery-Plat-1"),
            role=UserRole.PLATFORM_ADMIN,
            full_name="Platform Admin",
            is_email_verified=True,
        )
        db.add(platform_admin)
        db.commit()
    finally:
        db.close()

    login = client.post(
        "/api/v1/auth/login",
        json={"email": "platform-admin@caplink.internal", "password": "Correct-Horse-Battery-Plat-1"},
    )
    assert login.status_code == 200, login.text
    platform_admin_token = login.json()["access_token"]

    listed = client.get("/api/v1/universities", headers=_auth(platform_admin_token))
    assert listed.status_code == 200, listed.text
    assert any(u["id"] == university_id for u in listed.json())

    # A non-platform-admin (a plain student) must not be able to list every tenant.
    student_token = _register_student(client, university_slug="listeduni", email="listed-student@listeduni.ac.uk")
    forbidden = client.get("/api/v1/universities", headers=_auth(student_token))
    assert forbidden.status_code == 403, forbidden.text

    # Public branding needs no auth at all.
    public = client.get("/api/v1/universities/listeduni/public")
    assert public.status_code == 200, public.text
    assert public.json()["name"]

    public_missing = client.get("/api/v1/universities/does-not-exist/public")
    assert public_missing.status_code == 404, public_missing.text
