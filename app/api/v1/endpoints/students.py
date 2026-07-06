from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import require_student
from app.db.session import get_db
from app.models.user import StudentProfile, User
from app.schemas.user import StudentProfileOut, StudentProfileUpdate

router = APIRouter(prefix="/students", tags=["students"])


def _get_own_profile(db: Session, user: User) -> StudentProfile:
    profile = db.query(StudentProfile).filter(StudentProfile.user_id == user.id).first()
    if profile is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Student profile not found")
    return profile


@router.get("/me", response_model=StudentProfileOut)
def get_my_profile(db: Session = Depends(get_db), user: User = Depends(require_student)):
    return _get_own_profile(db, user)


@router.patch("/me", response_model=StudentProfileOut)
def update_my_profile(
    payload: StudentProfileUpdate, db: Session = Depends(get_db), user: User = Depends(require_student)
):
    profile = _get_own_profile(db, user)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(profile, field, value)
    db.commit()
    db.refresh(profile)
    return profile
