from datetime import date
from typing import Optional

from pydantic import BaseModel, ConfigDict, EmailStr

from app.models.enums import UniversityLicenseStatus, UniversityLicenseTier


class UniversityCreate(BaseModel):
    """Used by CAPLink platform admins to onboard a new licensed institution."""
    name: str
    slug: str
    domain: str
    primary_color: str = "#1B2A45"
    logo_url: Optional[str] = None
    license_tier: UniversityLicenseTier = UniversityLicenseTier.TRIAL
    license_seats: int = 500
    primary_contact_name: Optional[str] = None
    primary_contact_email: Optional[EmailStr] = None
    campus_postcode: Optional[str] = None  # geocoded server-side on creation


class UniversityOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    slug: str
    domain: str
    primary_color: str
    logo_url: Optional[str]
    license_tier: UniversityLicenseTier
    license_status: UniversityLicenseStatus
    license_seats: int
    contract_start: Optional[date]
    contract_end: Optional[date]
    postcode: Optional[str]
    latitude: Optional[float]
    longitude: Optional[float]


class UniversityLocationUpdate(BaseModel):
    """Set or refresh the campus postcode used as the centre point for local business search."""
    postcode: str


class UniversityPublicBranding(BaseModel):
    """Safe-to-expose subset for the public/unauthenticated landing page (subdomain)."""
    model_config = ConfigDict(from_attributes=True)

    name: str
    slug: str
    primary_color: str
    logo_url: Optional[str]
