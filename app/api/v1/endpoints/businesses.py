from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import require_business
from app.db.session import get_db
from app.models.user import BusinessProfile, User
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
