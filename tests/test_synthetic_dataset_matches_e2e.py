"""Workstream 9.c.i's automated counterpart to the live browser
click-through: posts the hero project through the real HTTP API against
the seeded synthetic dataset, and asserts the shortlist is genuinely
differentiated (not everyone scoring ~the same) with the hand-crafted
top match actually on top."""
from app.models.enums import ProjectCategory, StudentBand
from scripts import seed_demo_data

from tests.test_golden_path_e2e import _auth


def _login(client, email: str, password: str) -> str:
    resp = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert resp.status_code == 200, resp.text
    return resp.json()["access_token"]


def test_hero_project_produces_a_differentiated_shortlist_with_expected_top_match(client, db_session_factory):
    db = db_session_factory()
    summary = seed_demo_data.run(db=db)
    db.close()

    business_token = _login(client, summary.hero_business_email, summary.hero_business_password)

    db = db_session_factory()
    from app.models.university import University
    manchester_id = db.query(University.id).filter(University.slug == "manchester").scalar()
    db.close()

    post_resp = client.post(
        "/api/v1/projects",
        headers=_auth(business_token),
        json={
            "title": "Build a customer analytics dashboard",
            "description": (
                "We need an interactive dashboard that visualises customer engagement, retention "
                "and revenue trends from our subscription data, so our team can make faster, "
                "data-informed decisions without waiting on manual reports."
            ),
            "category": ProjectCategory.DATA_ANALYTICS.value,
            "required_skills": ["Python", "SQL", "Data Visualisation", "React"],
            "duration_label": "2-3 weeks",
            "estimated_hours": 20,
            "hourly_rate_gbp": 22,
            "target_university_ids": [manchester_id],
            "target_bands": [StudentBand.YEAR_3.value, StudentBand.YEAR_4_PLUS.value, StudentBand.POSTGRAD_TAUGHT.value],
        },
    )
    assert post_resp.status_code == 201, post_resp.text
    project_id = post_resp.json()["id"]

    shortlist_resp = client.get(f"/api/v1/projects/{project_id}/shortlist", headers=_auth(business_token))
    assert shortlist_resp.status_code == 200, shortlist_resp.text
    entries = shortlist_resp.json()

    assert len(entries) >= 3
    scores = [e["match_score"] for e in entries]
    assert scores == sorted(scores, reverse=True)  # already ranked
    assert scores[0] > scores[-1] + 0.15  # genuinely differentiated, not a flat line

    top_match = entries[0]
    assert top_match["full_name"] == "Priya Anand"
    assert top_match["match_score"] > 0.75

    ella = next(e for e in entries if e["full_name"] == "Ella Marsh")
    assert ella["match_score"] < top_match["match_score"] - 0.15
