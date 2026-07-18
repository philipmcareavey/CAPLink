from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import require_platform_admin, require_university_admin
from app.db.session import get_db
from app.models.university import University
from app.models.user import User
from app.schemas.university import (
    UniversityCreate,
    UniversityLocationUpdate,
    UniversityOut,
    UniversityPublicBranding,
)
from app.services import geo

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

    data = payload.model_dump(exclude={"campus_postcode"})
    university = University(**data)

    if payload.campus_postcode:
        geocoded = geo.geocode_postcode(payload.campus_postcode)
        if geocoded is None:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Could not verify campus postcode — check it's a valid UK postcode")
        university.postcode = geocoded.normalized_postcode
        university.latitude = geocoded.latitude
        university.longitude = geocoded.longitude

    db.add(university)
    db.commit()
    db.refresh(university)
    return university


@router.patch("/{university_id}/location", response_model=UniversityOut)
def update_campus_location(
    university_id: str,
    payload: UniversityLocationUpdate,
    db: Session = Depends(get_db),
    admin: User = Depends(require_university_admin),
):
    """A university admin sets or corrects their campus postcode — this is
    the centre point every local-business radius search is measured from."""
    if admin.university_id != university_id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "You can only manage your own university")

    university = db.query(University).filter(University.id == university_id).first()
    if university is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "University not found")

    geocoded = geo.geocode_postcode(payload.postcode)
    if geocoded is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Could not verify that postcode — check it's a valid UK postcode")

    university.postcode = geocoded.normalized_postcode
    university.latitude = geocoded.latitude
    university.longitude = geocoded.longitude
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
