from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.deps import Pagination, require_business, require_student
from app.db.session import get_db
from app.models.enums import ProjectStatus
from app.models.project import Project
from app.models.recommendation import RecommendationLog
from app.models.user import BusinessProfile, StudentProfile, User
from app.schemas.project import ProjectCreate, ProjectOut, ProjectWithMatch
from app.services import access_control, matching

router = APIRouter(prefix="/projects", tags=["projects"])


@router.post("", response_model=ProjectOut, status_code=status.HTTP_201_CREATED)
def create_project(
    payload: ProjectCreate,
    db: Session = Depends(get_db),
    business_user: User = Depends(require_business),
):
    business = db.query(BusinessProfile).filter(BusinessProfile.user_id == business_user.id).first()

    # Safeguarding gate: for every university this project targets, the
    # business must hold an approved agreement covering this category,
    # and every targeted band must be within that agreement's allowed bands.
    for uni_id in payload.target_university_ids:
        decision = access_control.can_business_post_category_for_university(
            db, business, uni_id, payload.category.value
        )
        if not decision.allowed:
            raise HTTPException(status.HTTP_403_FORBIDDEN, decision.reason)

        agreement = access_control.get_agreement(db, uni_id, business.id)
        disallowed_bands = [b.value for b in payload.target_bands if b.value not in agreement.allowed_bands]
        if disallowed_bands:
            raise HTTPException(
                status.HTTP_403_FORBIDDEN,
                f"Not approved for bands {disallowed_bands} at university {uni_id}",
            )

    needs_review = any(
        access_control.get_agreement(db, uid, business.id).requires_university_project_review
        for uid in payload.target_university_ids
    )

    project = Project(
        business_id=business.id,
        title=payload.title,
        description=payload.description,
        category=payload.category,
        required_skills=payload.required_skills,
        duration_label=payload.duration_label,
        estimated_hours=payload.estimated_hours,
        hourly_rate_gbp=payload.hourly_rate_gbp,
        is_remote=payload.is_remote,
        location_label=payload.location_label,
        target_university_ids=payload.target_university_ids,
        target_bands=[b.value for b in payload.target_bands],
        status=ProjectStatus.PENDING_REVIEW if needs_review else ProjectStatus.OPEN,
    )
    db.add(project)
    db.commit()
    db.refresh(project)
    return project


@router.get("/mine", response_model=list[ProjectOut])
def list_my_projects(db: Session = Depends(get_db), business_user: User = Depends(require_business)):
    """A business's own posted projects, newest first."""
    business = db.query(BusinessProfile).filter(BusinessProfile.user_id == business_user.id).first()
    return (
        db.query(Project)
        .filter(Project.business_id == business.id)
        .order_by(Project.created_at.desc())
        .all()
    )


@router.get("/feed", response_model=list[ProjectWithMatch])
def get_suggested_projects(
    db: Session = Depends(get_db),
    student_user: User = Depends(require_student),
    pagination: Pagination = Depends(),
):
    """
    The student's home feed: OPEN projects ranked by fit, restricted to
    what their university's safeguarding policy permits them to see at all,
    with mobile-friendly pagination baked in.
    """
    student = db.query(StudentProfile).filter(StudentProfile.user_id == student_user.id).first()

    candidate_projects = db.query(Project).filter(Project.status == ProjectStatus.OPEN).all()
    visible_projects = access_control.filter_projects_visible_to_student(student, candidate_projects)

    ranked = matching.rank_projects_for_student(student, visible_projects)

    page = ranked[pagination.offset : pagination.offset + pagination.page_size]

    results = []
    for project, match in page:
        log = RecommendationLog(
            user_id=student_user.id,
            entity_type="project",
            entity_id=project.id,
            score=match.score,
            reasons=match.reasons,
        )
        db.add(log)
        results.append(
            ProjectWithMatch(
                **ProjectOut.model_validate(project).model_dump(),
                match_score=match.score,
                match_reasons=match.reasons,
            )
        )
    db.commit()
    return results
