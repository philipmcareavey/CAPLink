from app.core.security import hash_password
from app.models.application import Application
from app.models.enums import ApplicationStatus, ProjectCategory, ProjectStatus, StudentBand, UserRole
from app.models.project import Project
from app.models.university import University
from app.models.user import BusinessProfile, StudentProfile, User
from app.services.matching.collaborative import collaborative_score
from app.services.matching.scorer import score_student_against_project


def _seed_university(db):
    uni = University(name="Test University", slug="test-uni", domain="test.ac.uk")
    db.add(uni)
    db.flush()
    return uni


def _seed_business(db):
    user = User(email="biz@example.com", hashed_password=hash_password("x"), role=UserRole.BUSINESS, full_name="Biz")
    db.add(user)
    db.flush()
    profile = BusinessProfile(user_id=user.id, company_name="TestCo")
    db.add(profile)
    db.flush()
    return profile


def _seed_student(db, uni, email, skills, avg_rating, completed_count):
    user = User(email=email, hashed_password=hash_password("x"), role=UserRole.STUDENT,
                full_name="Student", university_id=uni.id, is_email_verified=True)
    db.add(user)
    db.flush()
    profile = StudentProfile(
        user_id=user.id, university_id=uni.id, degree_title="BSc Data Science", band=StudentBand.YEAR_3,
        skills=skills, average_rating=avg_rating, completed_projects_count=completed_count,
    )
    db.add(profile)
    db.flush()
    return profile


def _seed_project(db, business, category=ProjectCategory.DATA_ANALYTICS, required_skills=None):
    project = Project(
        business_id=business.id, title="Some Project", description="desc",
        category=category, required_skills=required_skills or ["Python", "SQL"],
        duration_label="1-2 weeks", hourly_rate_gbp=18.0, status=ProjectStatus.OPEN,
    )
    db.add(project)
    db.flush()
    return project


def test_collaborative_score_is_none_with_no_history(db_session):
    uni = _seed_university(db_session)
    business = _seed_business(db_session)
    student = _seed_student(db_session, uni, "s1@test.ac.uk", ["Python"], 0.0, 0)
    project = _seed_project(db_session, business)
    db_session.commit()

    assert collaborative_score(db_session, student, project) is None


def test_collaborative_score_reflects_similar_students_success(db_session):
    uni = _seed_university(db_session)
    business = _seed_business(db_session)

    # Two similar-skilled students who succeeded (accepted + highly rated)
    # on past data_analytics projects.
    successful_1 = _seed_student(db_session, uni, "s1@test.ac.uk", ["Python", "SQL"], 4.8, 5)
    successful_2 = _seed_student(db_session, uni, "s2@test.ac.uk", ["Python", "SQL"], 4.9, 3)
    new_student = _seed_student(db_session, uni, "s3@test.ac.uk", ["Python", "SQL"], 0.0, 0)

    past_project_1 = _seed_project(db_session, business)
    past_project_2 = _seed_project(db_session, business)
    new_project = _seed_project(db_session, business)

    db_session.add(Application(project_id=past_project_1.id, student_id=successful_1.id,
                                status=ApplicationStatus.ACCEPTED))
    db_session.add(Application(project_id=past_project_2.id, student_id=successful_2.id,
                                status=ApplicationStatus.ACCEPTED))
    db_session.commit()

    score = collaborative_score(db_session, new_student, new_project)
    assert score is not None
    assert score > 0.8  # similar students rated ~4.8-4.9/5


def test_scorer_includes_collaborative_factor_when_db_and_data_available(db_session):
    uni = _seed_university(db_session)
    business = _seed_business(db_session)
    successful = _seed_student(db_session, uni, "s1@test.ac.uk", ["Python", "SQL"], 4.9, 5)
    new_student = _seed_student(db_session, uni, "s2@test.ac.uk", ["Python", "SQL"], 0.0, 0)
    past_project = _seed_project(db_session, business)
    new_project = _seed_project(db_session, business)

    db_session.add(Application(project_id=past_project.id, student_id=successful.id,
                                status=ApplicationStatus.ACCEPTED))
    db_session.commit()

    result = score_student_against_project(new_student, new_project, db=db_session)
    factor_names = [f.name for f in result.breakdown]
    assert "collaborative" in factor_names
