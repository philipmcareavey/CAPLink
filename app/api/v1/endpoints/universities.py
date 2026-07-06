from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import require_platform_admin
from app.db.session import get_db
from app.models.university import University
from app.schemas.university import UniversityCreate, UniversityOut, UniversityPublicBranding

router = APIRouter(prefix="/universities", tags=["universities"])


@router.get("/{slug}/public", response_model=UniversityPublicBranding)
def get_public_branding(slug: str, db: Session = Depends(get_db)):
    """
    Unauthenticated endpoint powering each university's branded landing page
    at {slug}.caplink.io — logo, name, colour, nothing sensitive.
    """
    university = db.query(University).filter(University.slug == slug).first()
    if university is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "University not found")
    return university


@router.post("", response_model=UniversityOut, status_code=status.HTTP_201_CREATED)
def onboard_university(
    payload: UniversityCreate,
    db: Session = Depends(get_db),
    _admin=Depends(require_platform_admin),
):
    """CAPLink platform-admin-only: onboard a new licensed institution."""
    if db.query(University).filter(University.slug == payload.slug).first():
        raise HTTPException(status.HTTP_409_CONFLICT, "Slug already taken")

    university = University(**payload.model_dump())
    db.add(university)
    db.commit()
    db.refresh(university)
    return university


@router.get("", response_model=list[UniversityOut])
def list_universities(db: Session = Depends(get_db), _admin=Depends(require_platform_admin)):
    return db.query(University).all()


@router.get("/{university_id}", response_model=UniversityOut)
def get_university(university_id: str, db: Session = Depends(get_db)):
    university = db.query(University).filter(University.id == university_id).first()
    if university is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "University not found")
    return university
