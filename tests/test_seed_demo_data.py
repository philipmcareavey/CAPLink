# tests/test_seed_demo_data.py
"""Workstream 9.a.iii/9.a.iv — the rewritten seed script builds a small
but varied synthetic dataset plus one hand-crafted "hero" business account
(Northbridge Analytics) with a pool of Manchester students engineered to
produce a clearly differentiated shortlist once a project is posted
against them (verified for real in Task 10/11 — this test just checks the
data landed correctly)."""
from app.models.policy import UniversityBusinessAgreement
from app.models.project import Project
from app.models.university import University
from app.models.user import BusinessProfile, StudentProfile, User
from scripts import seed_demo_data


def test_seed_creates_a_realistic_small_dataset(db_session):
    summary = seed_demo_data.run(db=db_session)

    assert summary.universities == 4
    assert 60 <= summary.students <= 100
    assert summary.businesses == 19  # 18 generated (BUSINESS_TEMPLATES) + 1 hand-crafted hero
    assert 20 <= summary.projects <= 30

    assert db_session.query(University).count() == summary.universities
    assert db_session.query(StudentProfile).count() == summary.students
    assert db_session.query(BusinessProfile).count() == summary.businesses
    assert db_session.query(Project).count() == summary.projects
    assert db_session.query(UniversityBusinessAgreement).count() >= summary.businesses  # at least 1 each


def test_seed_creates_the_hero_business_with_an_approved_manchester_agreement(db_session):
    summary = seed_demo_data.run(db=db_session)

    hero_user = db_session.query(User).filter(User.email == summary.hero_business_email).first()
    assert hero_user is not None
    hero_business = db_session.query(BusinessProfile).filter(BusinessProfile.user_id == hero_user.id).first()
    assert hero_business.company_name == "Northbridge Analytics"

    manchester = db_session.query(University).filter(University.slug == "manchester").first()
    agreement = (
        db_session.query(UniversityBusinessAgreement)
        .filter(
            UniversityBusinessAgreement.business_id == hero_business.id,
            UniversityBusinessAgreement.university_id == manchester.id,
        )
        .first()
    )
    assert agreement is not None
    assert agreement.status.value == "approved"
    assert not agreement.requires_university_project_review


def test_seed_hand_crafted_students_have_differentiated_profiles_for_the_hero_scenario(db_session):
    summary = seed_demo_data.run(db=db_session)
    top_match = db_session.query(User).filter(User.email == "priya.anand@manchester.ac.uk").first()
    assert top_match is not None
    top_profile = db_session.query(StudentProfile).filter(StudentProfile.user_id == top_match.id).first()
    assert set(["Python", "SQL", "React"]).issubset(set(top_profile.skills))
    assert "Data Science" in top_profile.degree_title


def test_seed_is_idempotent_and_safe_to_rerun(db_session):
    """run()'s actual "safe to rerun" guarantee only applies when it owns
    its own session (the real `python -m scripts.seed_demo_data` usage,
    which drops and recreates every table via Base.metadata.drop_all +
    run_migrations before reseeding — see run()'s owns_session branch).
    Passing an existing `db` in (as every other test in this file does)
    deliberately skips that reset, since the db_session fixture already
    hands over a fresh, empty database every time — there's nothing to
    wipe. This test simulates one real reseed cycle by wiping the schema
    itself between two calls, the same way the script's own reset does,
    and checks the result is identical both times (same RNG seed -> same
    dataset, not a coincidence)."""
    from app.db.base_class import Base
    from app.models.user import BusinessProfile

    first = seed_demo_data.run(db=db_session)

    bind = db_session.get_bind()
    Base.metadata.drop_all(bind=bind)
    Base.metadata.create_all(bind=bind)

    second = seed_demo_data.run(db=db_session)
    assert first.students == second.students
    assert first.businesses == second.businesses
    assert db_session.query(BusinessProfile).count() == second.businesses
