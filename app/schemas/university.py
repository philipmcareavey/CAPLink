from datetime import date
from typing import Annotated, Optional

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.models.enums import UniversityLicenseStatus, UniversityLicenseTier


class UniversityCreate(BaseModel):
    """Used by CAPLink platform admins to onboard a new licensed institution."""
    name: str = Field(min_length=1, max_length=200)
    slug: str = Field(min_length=1, max_length=100, pattern=r"^[a-z0-9-]+$")
    domain: str = Field(min_length=1, max_length=255)
    primary_color: str = Field(default="#1B2A45", max_length=20)
    logo_url: Optional[str] = Field(default=None, max_length=500)
    license_tier: UniversityLicenseTier = UniversityLicenseTier.TRIAL
    license_seats: int = Field(default=500, ge=0, le=1_000_000)
    primary_contact_name: Optional[str] = Field(default=None, max_length=200)
    primary_contact_email: Optional[EmailStr] = None
    campus_postcode: Optional[str] = Field(default=None, max_length=20)  # geocoded server-side on creation


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
    postcode: str = Field(min_length=1, max_length=20)


class UniversityPublicBranding(BaseModel):
    """Safe-to-expose subset for the public/unauthenticated landing page (subdomain)."""
    model_config = ConfigDict(from_attributes=True)

    name: str
    slug: str
    primary_color: str
    logo_url: Optional[str]
    saml_enabled: bool  # lets a login screen decide whether to show "Sign in with your university"


# ---------- SAML SSO config (2.b) ----------

class SamlConfigUpdate(BaseModel):
    """Manual entry — the alternative to uploading the IdP's metadata XML
    directly (see SamlMetadataUpload) when an admin already has these three
    values to hand."""
    saml_enabled: bool = True
    saml_idp_entity_id: str = Field(min_length=1, max_length=500)
    saml_idp_sso_url: str = Field(min_length=1, max_length=500)
    saml_idp_x509_cert: str = Field(min_length=1, max_length=10_000)
    saml_attribute_mapping: Optional[dict[Annotated[str, Field(max_length=100)], Annotated[str, Field(max_length=200)]]] = Field(
        default=None, max_length=50
    )


class SamlMetadataUpload(BaseModel):
    """2.b.iv's backend half — the actual upload *screen* is a Workstream 5
    (frontend) concern; this is the endpoint it would call. metadata_xml is
    capped well above any real IdP metadata document (Technical
    Implementation Plan 2.c.ii oversized-payload hardening) — note
    python3-saml's underlying parser (app/services/saml.py's
    parse_idp_metadata) already forbids DTDs/external entities regardless,
    so this cap is a defence-in-depth memory/parse-time bound, not the only
    thing standing between this endpoint and an XXE/entity-expansion attack."""
    metadata_xml: str = Field(min_length=1, max_length=2_000_000)
    saml_enabled: bool = True


class SamlConfigOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    saml_enabled: bool
    saml_idp_entity_id: Optional[str]
    saml_idp_sso_url: Optional[str]
    saml_attribute_mapping: Optional[dict]
    # x509cert deliberately excluded — long, and not something a caller
    # ever needs handed back to them.
