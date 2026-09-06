from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import require_platform_admin, require_university_admin
from app.db.session import get_db
from app.models.university import University
from app.models.user import User
from app.schemas.university import (
    SamlConfigOut,
    SamlConfigUpdate,
    SamlMetadataUpload,
    UniversityCreate,
    UniversityLocationUpdate,
    UniversityOut,
    UniversityPublicBranding,
)
from app.services import geo
from app.services import saml as saml_service

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


@router.patch("/{university_id}/saml-config", response_model=SamlConfigOut)
def update_saml_config(
    university_id: str,
    payload: SamlConfigUpdate,
    db: Session = Depends(get_db),
    admin: User = Depends(require_university_admin),
):
    """Manual entry of a university's IdP details (Technical Implementation
    Plan 2.b.iii/2.b.iv) — see POST .../saml-idp-metadata for uploading the
    IdP's metadata XML directly instead of copying these three fields by hand."""
    if admin.university_id != university_id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "You can only manage your own university")

    university = db.query(University).filter(University.id == university_id).first()
    if university is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "University not found")

    university.saml_enabled = payload.saml_enabled
    university.saml_idp_entity_id = payload.saml_idp_entity_id
    university.saml_idp_sso_url = payload.saml_idp_sso_url
    university.saml_idp_x509_cert = payload.saml_idp_x509_cert
    university.saml_attribute_mapping = payload.saml_attribute_mapping
    db.commit()
    db.refresh(university)
    return university


@router.post("/{university_id}/saml-idp-metadata", response_model=SamlConfigOut)
def upload_saml_idp_metadata(
    university_id: str,
    payload: SamlMetadataUpload,
    db: Session = Depends(get_db),
    admin: User = Depends(require_university_admin),
):
    """2.b.iv's backend half — a university IT team exports one XML file
    from their IdP; this extracts the entity ID, SSO URL, and certificate
    from it automatically rather than requiring manual, error-prone
    (especially the certificate) copy-pasting into three separate fields."""
    if admin.university_id != university_id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "You can only manage your own university")

    university = db.query(University).filter(University.id == university_id).first()
    if university is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "University not found")

    try:
        parsed = saml_service.parse_idp_metadata(payload.metadata_xml)
    except ValueError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc))

    university.saml_idp_entity_id = parsed["entity_id"]
    university.saml_idp_sso_url = parsed["sso_url"]
    university.saml_idp_x509_cert = parsed["x509_cert"]
    university.saml_enabled = payload.saml_enabled
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
