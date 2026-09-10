from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import require_business, require_student
from app.db.session import get_db
from app.models.application import Application
from app.models.project import Project
from app.models.university import University
from app.models.user import BusinessProfile, StudentProfile, User
from app.schemas.application import (
    ApplicantOut,
    ApplicationCreate,
    ApplicationOut,
    ApplicationStatusUpdate,
    StudentShortlistEntry,
)
from app.schemas.project import MatchExplanationOut, MatchFactorOut
from app.services import access_control, matching
from app.services.notifications import notify_from_template

router = APIRouter(tags=["applications"])


@router.post("/applications", response_model=ApplicationOut, status_code=status.HTTP_201_CREATED)
def apply_to_project(
    payload: ApplicationCreate, db: Session = Depends(get_db), student_user: User = Depends(require_student)
):
    """Applies to an OPEN project the student can actually see — 403s if
    the safeguarding gate wouldn't show it to them at all, regardless of
    whether it's technically open."""
    student = db.query(StudentProfile).filter(StudentProfile.user_id == student_user.id).first()
    assert student is not None, "require_student guarantees a StudentProfile row exists"
    project = db.query(Project).filter(Project.id == payload.project_id).first()
    if project is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Project not found")

    visible = access_control.filter_projects_visible_to_student(student, [project])
    if not visible:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "This project is not available to your university/band")

    match = matching.score_student_against_project(student, project, db=db)

    application = Application(
        project_id=project.id,
        student_id=student.id,
        cover_note=payload.cover_note,
        proposed_rate_gbp=payload.proposed_rate_gbp,
        match_score_at_application=match.score,
    )
    db.add(application)
    db.commit()
    db.refresh(application)

    business_user_id = db.query(BusinessProfile.user_id).filter(BusinessProfile.id == project.business_id).scalar()
    notify_from_template(db, business_user_id, "new_match", title=project.title)
    return application


@router.get("/projects/{project_id}/shortlist", response_model=list[StudentShortlistEntry])
def get_shortlist(
    project_id: str, db: Session = Depends(get_db), business_user: User = Depends(require_business)
):
    """Every visible candidate the matching engine would recommend for
    this project, ranked — not just students who've actually applied (see
    GET .../applications for that). See also the .../explanation endpoint
    below for a per-candidate scoring breakdown."""
    business = db.query(BusinessProfile).filter(BusinessProfile.user_id == business_user.id).first()
    assert business is not None, "require_business guarantees a BusinessProfile row exists"
    project = db.query(Project).filter(Project.id == project_id, Project.business_id == business.id).first()
    if project is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Project not found")

    candidate_students = (
        db.query(StudentProfile).filter(StudentProfile.university_id.in_(project.target_university_ids)).all()
    )
    visible_students = access_control.filter_students_visible_to_business(db, business, candidate_students)

    ranked = matching.rank_students_for_project(project, visible_students, db=db)

    results = []
    for student, match in ranked:
        university_name = db.query(University.name).filter(University.id == student.university_id).scalar()
        results.append(
            StudentShortlistEntry(
                student_id=student.id,
                full_name=student.user.full_name,
                degree_title=student.degree_title,
                university_name=university_name or "",
                average_rating=student.average_rating,
                completed_projects_count=student.completed_projects_count,
                match_score=match.score,
                match_reasons=match.reasons,
            )
        )
    return results


@router.get("/projects/{project_id}/shortlist/{student_id}/explanation", response_model=MatchExplanationOut)
def get_shortlist_candidate_explanation(
    project_id: str, student_id: str, db: Session = Depends(get_db), business_user: User = Depends(require_business)
):
    """Technical Implementation Plan 5.c.ii's drill-down — the business-side
    counterpart to projects.py::get_match_explanation, which is student-only
    (it scores the *calling* student against a project, with no student_id
    parameter at all, so a business could never have called it for a
    specific shortlist candidate). Same underlying scorer, same response
    shape, different caller and an explicit student_id plus the same
    safeguarding visibility check get_shortlist itself applies."""
    business = db.query(BusinessProfile).filter(BusinessProfile.user_id == business_user.id).first()
    assert business is not None, "require_business guarantees a BusinessProfile row exists"
    project = db.query(Project).filter(Project.id == project_id, Project.business_id == business.id).first()
    if project is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Project not found")

    student = db.query(StudentProfile).filter(StudentProfile.id == student_id).first()
    if student is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Student not found")
    if not access_control.filter_students_visible_to_business(db, business, [student]):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "This student is not visible to your business")

    match = matching.score_student_against_project(student, project, db=db)
    return MatchExplanationOut(
        score=match.score,
        algorithm_version=match.algorithm_version,
        reasons=match.reasons,
        breakdown=[
            MatchFactorOut(
                name=f.name, raw_score=f.raw_score, weight=f.weight,
                contribution=f.contribution, detail=f.detail,
            )
            for f in match.breakdown
        ],
    )


@router.get("/projects/{project_id}/applications", response_model=list[ApplicantOut])
def get_project_applications(
    project_id: str, db: Session = Depends(get_db), business_user: User = Depends(require_business)
):
    """Real applicants to this project — not candidates (see get_shortlist
    above), actual Application rows, for a business to review and act on."""
    business = db.query(BusinessProfile).filter(BusinessProfile.user_id == business_user.id).first()
    assert business is not None, "require_business guarantees a BusinessProfile row exists"
    project = db.query(Project).filter(Project.id == project_id).first()
    if project is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Project not found")
    if project.business_id != business.id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Not your project")

    applications = (
        db.query(Application)
        .filter(Application.project_id == project_id)
        .order_by(Application.created_at.desc())
        .all()
    )

    results = []
    for application in applications:
        student = db.query(StudentProfile).filter(StudentProfile.id == application.student_id).first()
        assert student is not None, "Application.student_id is a NOT NULL FK to student_profiles"
        results.append(
            ApplicantOut(
                application_id=application.id,
                student_id=student.id,
                student_user_id=student.user_id,
                full_name=student.user.full_name,
                degree_title=student.degree_title,
                status=application.status,
                cover_note=application.cover_note,
                proposed_rate_gbp=application.proposed_rate_gbp,
                match_score_at_application=application.match_score_at_application,
            )
        )
    return results


@router.patch("/applications/{application_id}", response_model=ApplicationOut)
def update_application_status(
    application_id: str,
    payload: ApplicationStatusUpdate,
    db: Session = Depends(get_db),
    business_user: User = Depends(require_business),
):
    """Moves an application through its status pipeline (shortlisted,
    interviewing, offered, etc.) — business-only, and only for the
    business's own project."""
    application = db.query(Application).filter(Application.id == application_id).first()
    if application is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Application not found")

    business = db.query(BusinessProfile).filter(BusinessProfile.user_id == business_user.id).first()
    assert business is not None, "require_business guarantees a BusinessProfile row exists"
    project = db.query(Project).filter(Project.id == application.project_id).first()
    assert project is not None, "Application.project_id is a NOT NULL FK to projects"
    if project.business_id != business.id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Not your project")

    application.status = payload.status
    db.commit()
    db.refresh(application)

    student_user_id = db.query(StudentProfile.user_id).filter(StudentProfile.id == application.student_id).scalar()
    notify_from_template(db, student_user_id, "application_status", title=project.title, status=payload.status.value)
    return application
