from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import require_business
from app.db.session import get_db
from app.models.policy import UniversityBusinessAgreement
from app.models.university import University
from app.models.user import BusinessProfile, User
from app.schemas.policy import AgreementWithUniversityOut
from app.schemas.user import BusinessProfileOut, BusinessProfileUpdate
from app.services import geo

router = APIRouter(prefix="/businesses", tags=["businesses"])


def _get_own_profile(db: Session, user: User) -> BusinessProfile:
    profile = db.query(BusinessProfile).filter(BusinessProfile.user_id == user.id).first()
    if profile is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Business profile not found")
    return profile


@router.get("/me", response_model=BusinessProfileOut)
def get_my_profile(db: Session = Depends(get_db), user: User = Depends(require_business)):
    """The calling business's own profile — trust tier, rating history
    summary, and the postcode used for the local-search feature."""
    return _get_own_profile(db, user)


@router.patch("/me", response_model=BusinessProfileOut)
def update_my_profile(
    payload: BusinessProfileUpdate, db: Session = Depends(get_db), user: User = Depends(require_business)
):
    """
    Setting/changing `postcode` here is what makes this business eligible to
    appear in a university's "local businesses near campus" radius search —
    it's geocoded immediately so results stay fast (no on-request lookups).
    A business that never sets a postcode (e.g. fully remote) simply never
    appears in radius results, which is the correct behaviour, not an error.
    """
    profile = _get_own_profile(db, user)
    updates = payload.model_dump(exclude_unset=True)

    new_postcode = updates.pop("postcode", None)
    for field, value in updates.items():
        setattr(profile, field, value)

    if new_postcode is not None:
        if new_postcode == "":
            profile.postcode, profile.latitude, profile.longitude = None, None, None
        else:
            geocoded = geo.geocode_postcode(new_postcode)
            if geocoded is None:
                raise HTTPException(
                    status.HTTP_400_BAD_REQUEST, "Could not verify that postcode — check it's a valid UK postcode"
                )
            profile.postcode = geocoded.normalized_postcode
            profile.latitude = geocoded.latitude
            profile.longitude = geocoded.longitude

    db.commit()
    db.refresh(profile)
    return profile


@router.get("/me/agreements", response_model=list[AgreementWithUniversityOut])
def get_my_agreements(db: Session = Depends(get_db), business_user: User = Depends(require_business)):
    """Every agreement this business holds, across every university —
    lets the mobile/web post-project flow show real, valid targets
    instead of guessing a university id from a slug lookup."""
    business = db.query(BusinessProfile).filter(BusinessProfile.user_id == business_user.id).first()
    assert business is not None, "require_business guarantees a BusinessProfile row exists"

    rows = (
        db.query(UniversityBusinessAgreement, University.name)
        .join(University, University.id == UniversityBusinessAgreement.university_id)
        .filter(UniversityBusinessAgreement.business_id == business.id)
        .all()
    )
    return [
        AgreementWithUniversityOut(
            id=agreement.id,
            university_id=agreement.university_id,
            business_id=agreement.business_id,
            status=agreement.status,
            allowed_bands=agreement.allowed_bands,
            allowed_categories=agreement.allowed_categories,
            max_active_projects=agreement.max_active_projects,
            requires_university_project_review=agreement.requires_university_project_review,
            university_name=university_name,
        )
        for agreement, university_name in rows
    ]
