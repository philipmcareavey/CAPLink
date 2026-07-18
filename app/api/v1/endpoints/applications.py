from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import require_business, require_student
from app.db.session import get_db
from app.models.application import Application
from app.models.project import Project
from app.models.university import University
from app.models.user import BusinessProfile, StudentProfile, User
from app.schemas.application import ApplicationCreate, ApplicationOut, ApplicationStatusUpdate, StudentShortlistEntry
from app.services import access_control, matching
from app.services.notifications import notify_from_template

router = APIRouter(tags=["applications"])


@router.post("/applications", response_model=ApplicationOut, status_code=status.HTTP_201_CREATED)
def apply_to_project(
    payload: ApplicationCreate, db: Session = Depends(get_db), student_user: User = Depends(require_student)
):
    student = db.query(StudentProfile).filter(StudentProfile.user_id == student_user.id).first()
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
    business = db.query(BusinessProfile).filter(BusinessProfile.user_id == business_user.id).first()
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


@router.patch("/applications/{application_id}", response_model=ApplicationOut)
def update_application_status(
    application_id: str,
    payload: ApplicationStatusUpdate,
    db: Session = Depends(get_db),
    business_user: User = Depends(require_business),
):
    application = db.query(Application).filter(Application.id == application_id).first()
    if application is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Application not found")

    business = db.query(BusinessProfile).filter(BusinessProfile.user_id == business_user.id).first()
    project = db.query(Project).filter(Project.id == application.project_id).first()
    if project.business_id != business.id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Not your project")

    application.status = payload.status
    db.commit()
    db.refresh(application)

    student_user_id = db.query(StudentProfile.user_id).filter(StudentProfile.id == application.student_id).scalar()
    notify_from_template(db, student_user_id, "application_status", title=project.title, status=payload.status.value)
    return application
