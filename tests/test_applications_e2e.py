"""Technical Implementation Plan 8.a.i — the actual hiring-decision surface
(a business browsing candidates, reviewing real applicants, and moving an
application through its status pipeline) through the real HTTP API. Before
this file, test_golden_path_e2e.py's coverage of applications began and
ended at POST /applications — nothing exercised GET .../shortlist,
GET .../applications, or PATCH /applications/{id} at all.
"""
from app.models.enums import ProjectCategory, StudentBand

from tests.test_golden_path_e2e import _approve_agreement, _auth, _register_business, _register_student, _seed_university


def _post_project(client, *, business_token, university_id, title="Shortlist test project"):
    resp = client.post(
        "/api/v1/projects",
        headers=_auth(business_token),
        json={
            "title": title,
            "description": "Covers the shortlist/applications/decision endpoints.",
            "category": ProjectCategory.SOFTWARE_ENGINEERING.value,
            "required_skills": ["Python"],
            "duration_label": "1 week",
            "hourly_rate_gbp": 20,
            "target_university_ids": [university_id],
            "target_bands": [StudentBand.YEAR_3.value],
        },
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


def test_shortlist_ranks_visible_candidates_regardless_of_whether_they_applied(client):
    university_id = _seed_university(client, slug="shortlistuni", domain="shortlistuni.ac.uk")
    business_token = _register_business(client, email="shortlist-business@example.com")
    _approve_agreement(
        client,
        business_user_email="shortlist-business@example.com",
        university_id=university_id,
        bands=[StudentBand.YEAR_3.value],
        categories=[ProjectCategory.SOFTWARE_ENGINEERING.value],
    )
    project = _post_project(client, business_token=business_token, university_id=university_id)

    # A student who never applies still shows up on the shortlist — it
    # ranks every visible candidate, not just actual applicants.
    _register_student(client, university_slug="shortlistuni", email="never-applies@shortlistuni.ac.uk")

    shortlist = client.get(f"/api/v1/projects/{project['id']}/shortlist", headers=_auth(business_token))
    assert shortlist.status_code == 200, shortlist.text
    entries = shortlist.json()
    assert any(e["full_name"] for e in entries)
    student_id = entries[0]["student_id"]

    explanation = client.get(
        f"/api/v1/projects/{project['id']}/shortlist/{student_id}/explanation", headers=_auth(business_token)
    )
    assert explanation.status_code == 200, explanation.text
    assert "score" in explanation.json() and "breakdown" in explanation.json()

    # A second, unrelated business must not be able to browse this project's shortlist at all.
    intruder_token = _register_business(client, email="shortlist-intruder@example.com")
    forbidden = client.get(f"/api/v1/projects/{project['id']}/shortlist", headers=_auth(intruder_token))
    assert forbidden.status_code == 404, forbidden.text


def test_application_status_pipeline_via_real_http(client):
    university_id = _seed_university(client, slug="pipelineuni", domain="pipelineuni.ac.uk")
    business_token = _register_business(client, email="pipeline-business@example.com")
    _approve_agreement(
        client,
        business_user_email="pipeline-business@example.com",
        university_id=university_id,
        bands=[StudentBand.YEAR_3.value],
        categories=[ProjectCategory.SOFTWARE_ENGINEERING.value],
    )
    project = _post_project(client, business_token=business_token, university_id=university_id)
    student_token = _register_student(client, university_slug="pipelineuni", email="applicant@pipelineuni.ac.uk")

    apply_resp = client.post(
        "/api/v1/applications",
        headers=_auth(student_token),
        json={"project_id": project["id"], "cover_note": "Very keen."},
    )
    assert apply_resp.status_code == 201, apply_resp.text
    application_id = apply_resp.json()["id"]
    assert apply_resp.json()["status"] == "submitted"

    applicants = client.get(f"/api/v1/projects/{project['id']}/applications", headers=_auth(business_token))
    assert applicants.status_code == 200, applicants.text
    assert len(applicants.json()) == 1
    assert applicants.json()[0]["application_id"] == application_id
    assert applicants.json()[0]["cover_note"] == "Very keen."

    shortlisted = client.patch(
        f"/api/v1/applications/{application_id}", headers=_auth(business_token), json={"status": "shortlisted"}
    )
    assert shortlisted.status_code == 200, shortlisted.text
    assert shortlisted.json()["status"] == "shortlisted"

    rejected = client.patch(
        f"/api/v1/applications/{application_id}", headers=_auth(business_token), json={"status": "rejected"}
    )
    assert rejected.status_code == 200, rejected.text
    assert rejected.json()["status"] == "rejected"


def test_a_business_cannot_see_or_decide_another_businesss_applications(client):
    university_id = _seed_university(client, slug="pipelineuniown", domain="pipelineuniown.ac.uk")
    owner_token = _register_business(client, email="pipeline-owner@example.com")
    _approve_agreement(
        client,
        business_user_email="pipeline-owner@example.com",
        university_id=university_id,
        bands=[StudentBand.YEAR_3.value],
        categories=[ProjectCategory.SOFTWARE_ENGINEERING.value],
    )
    project = _post_project(client, business_token=owner_token, university_id=university_id)
    student_token = _register_student(
        client, university_slug="pipelineuniown", email="applicant2@pipelineuniown.ac.uk"
    )
    application_id = client.post(
        "/api/v1/applications", headers=_auth(student_token), json={"project_id": project["id"]}
    ).json()["id"]

    intruder_token = _register_business(client, email="pipeline-intruder@example.com")

    forbidden_list = client.get(
        f"/api/v1/projects/{project['id']}/applications", headers=_auth(intruder_token)
    )
    assert forbidden_list.status_code == 403, forbidden_list.text

    forbidden_decide = client.patch(
        f"/api/v1/applications/{application_id}", headers=_auth(intruder_token), json={"status": "rejected"}
    )
    assert forbidden_decide.status_code == 403, forbidden_decide.text
