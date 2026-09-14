"""Workstream 9.b.ii/iii — every real write path that creates or edits a
student profile or a project must end up with a cached `embedding` (when
sentence-transformers is installed) so the matching engine's semantic
factor actually has something to read. This test skips its assertions
(rather than failing) when the model isn't installed in this environment,
matching tests/test_embeddings.py's existing pattern."""
from app.models.enums import ProjectCategory, StudentBand
from app.models.project import Project
from app.models.user import StudentProfile
from app.services.matching import embeddings

from tests.test_golden_path_e2e import _auth, _register_business, _register_student, _seed_university
from tests.test_applications_e2e import _approve_agreement, _post_project


def test_student_registration_populates_embedding(client, db_session_factory):
    if not embeddings.is_available():
        return
    university_id = _seed_university(client, slug="embeduni", domain="embeduni.ac.uk")
    _register_student(client, university_slug="embeduni", email="embed-student@embeduni.ac.uk")

    db = db_session_factory()
    student = db.query(StudentProfile).filter(StudentProfile.university_id == university_id).first()
    assert student is not None
    assert student.embedding is not None
    assert len(student.embedding) > 0
    db.close()


def test_profile_update_recomputes_embedding(client, db_session_factory):
    if not embeddings.is_available():
        return
    _seed_university(client, slug="embedupdateuni", domain="embedupdateuni.ac.uk")
    token = _register_student(client, university_slug="embedupdateuni", email="embed-update@embedupdateuni.ac.uk")

    resp = client.patch(
        "/api/v1/students/me", headers=_auth(token), json={"skills": ["Python", "SQL", "React"]},
    )
    assert resp.status_code == 200, resp.text

    db = db_session_factory()
    student = db.query(StudentProfile).filter(StudentProfile.user_id.isnot(None)).order_by(StudentProfile.created_at.desc()).first()
    assert student.skills == ["Python", "SQL", "React"]
    assert student.embedding is not None
    db.close()


def test_project_creation_populates_embedding(client, db_session_factory):
    if not embeddings.is_available():
        return
    university_id = _seed_university(client, slug="embedprojuni", domain="embedprojuni.ac.uk")
    business_token = _register_business(client, email="embed-project-business@example.com")
    _approve_agreement(
        client, business_user_email="embed-project-business@example.com", university_id=university_id,
        bands=[StudentBand.YEAR_3.value], categories=[ProjectCategory.SOFTWARE_ENGINEERING.value],
    )
    project = _post_project(client, business_token=business_token, university_id=university_id)

    db = db_session_factory()
    row = db.query(Project).filter(Project.id == project["id"]).first()
    assert row.embedding is not None
    assert len(row.embedding) > 0
    db.close()
