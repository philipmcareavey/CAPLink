from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import require_business, require_university_admin
from app.db.session import get_db
from app.models.enums import AgreementStatus
from app.models.policy import UniversityBusinessAgreement
from app.models.user import BusinessProfile, User
from app.schemas.policy import AgreementCreate, AgreementDecision, AgreementOut

router = APIRouter(tags=["safeguarding-policies"])


@router.post(
    "/universities/{university_id}/business-agreements",
    response_model=AgreementOut,
    status_code=status.HTTP_201_CREATED,
)
def request_access(
    university_id: str,
    payload: AgreementCreate,
    db: Session = Depends(get_db),
    business_user: User = Depends(require_business),
):
    """A business requests permission to interact with a university's students.
    Starts PENDING — no access is granted until a university admin approves it
    and sets the allowed student bands / project categories."""
    business = db.query(BusinessProfile).filter(BusinessProfile.user_id == business_user.id).first()
    assert business is not None, "require_business guarantees a BusinessProfile row exists"

    existing = (
        db.query(UniversityBusinessAgreement)
        .filter(
            UniversityBusinessAgreement.university_id == university_id,
            UniversityBusinessAgreement.business_id == business.id,
        )
        .first()
    )
    if existing:
        raise HTTPException(status.HTTP_409_CONFLICT, "An agreement already exists — check its status")

    agreement = UniversityBusinessAgreement(
        university_id=university_id,
        business_id=business.id,
        status=AgreementStatus.PENDING,
    )
    db.add(agreement)
    db.commit()
    db.refresh(agreement)
    return agreement


@router.get(
    "/universities/{university_id}/business-agreements",
    response_model=list[AgreementOut],
)
def list_agreements(
    university_id: str,
    db: Session = Depends(get_db),
    _admin: User = Depends(require_university_admin),
):
    """University admin console: view every business partnership request."""
    return (
        db.query(UniversityBusinessAgreement)
        .filter(UniversityBusinessAgreement.university_id == university_id)
        .all()
    )


@router.patch(
    "/universities/{university_id}/business-agreements/{agreement_id}",
    response_model=AgreementOut,
)
def decide_agreement(
    university_id: str,
    agreement_id: str,
    payload: AgreementDecision,
    db: Session = Depends(get_db),
    admin: User = Depends(require_university_admin),
):
    """
    The core safeguarding control panel action: a university careers-team
    admin approves a business and defines EXACTLY which student bands
    (year groups / postgrad / alumni) and project categories it may access.
    """
    if admin.university_id != university_id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "You can only manage agreements for your own university")

    agreement = (
        db.query(UniversityBusinessAgreement)
        .filter(
            UniversityBusinessAgreement.id == agreement_id,
            UniversityBusinessAgreement.university_id == university_id,
        )
        .first()
    )
    if agreement is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Agreement not found")

    agreement.status = payload.status
    agreement.allowed_bands = [b.value for b in payload.allowed_bands]
    agreement.allowed_categories = [c.value for c in payload.allowed_categories]
    agreement.max_active_projects = payload.max_active_projects
    agreement.requires_university_project_review = payload.requires_university_project_review
    agreement.university_notes = payload.university_notes
    agreement.reviewed_by_admin_id = admin.id

    db.commit()
    db.refresh(agreement)
    return agreement
