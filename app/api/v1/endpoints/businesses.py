from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import require_business
from app.db.session import get_db
from app.models.user import BusinessProfile, User
from app.schemas.user import BusinessProfileOut

router = APIRouter(prefix="/businesses", tags=["businesses"])


@router.get("/me", response_model=BusinessProfileOut)
def get_my_profile(db: Session = Depends(get_db), user: User = Depends(require_business)):
    profile = db.query(BusinessProfile).filter(BusinessProfile.user_id == user.id).first()
    if profile is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Business profile not found")
    return profile
