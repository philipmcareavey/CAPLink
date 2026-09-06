from datetime import date
from typing import List, Optional, TYPE_CHECKING

from sqlalchemy import Boolean, Date, Float, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.models.enums import UniversityLicenseStatus, UniversityLicenseTier

if TYPE_CHECKING:
    from app.models.policy import UniversityBusinessAgreement


class University(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """
    A licensed institutional tenant, e.g. 'University of Manchester'.

    CAPLink is sold to universities the way Blackboard/Canvas is: each
    institution licenses the platform, gets a branded portal at
    {slug}.caplink.io, and its careers team gets an admin console to manage
    safeguarding policies, approve business partners, and pull employability
    reporting for its own students only.
    """
    __tablename__ = "universities"

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)  # subdomain
    domain: Mapped[str] = mapped_column(String(255), nullable=False)  # e.g. "manchester.ac.uk" — verifies student emails

    # Branding (white-label)
    primary_color: Mapped[str] = mapped_column(String(9), default="#1B2A45")
    logo_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)

    # Licensing
    license_tier: Mapped[UniversityLicenseTier] = mapped_column(default=UniversityLicenseTier.TRIAL)
    license_status: Mapped[UniversityLicenseStatus] = mapped_column(default=UniversityLicenseStatus.PENDING)
    license_seats: Mapped[int] = mapped_column(default=500)  # max active student accounts
    contract_start: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    contract_end: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    annual_fee_gbp: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    # Careers-service contact
    primary_contact_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    primary_contact_email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # Campus location — powers the postcode-radius local business search.
    # latitude/longitude are geocoded from postcode via app/services/geo.py
    # and cached here so radius search doesn't re-geocode on every request.
    postcode: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    latitude: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    longitude: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    business_agreements: Mapped[List["UniversityBusinessAgreement"]] = relationship(
        back_populates="university", cascade="all, delete-orphan"
    )

    # --- SAML SSO (Technical Implementation Plan 2.b) ---
    # All nullable/False by default: SSO is additive (2.b.iii), never a hard
    # replacement for email/password — a university with none of this
    # configured just keeps using /auth/login exactly as before.
    saml_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    saml_idp_entity_id: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    saml_idp_sso_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    # PEM-ish, no headers required — see app/services/saml.py's normaliser.
    saml_idp_x509_cert: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    # Maps CAPLink fields (email/full_name/band/degree_title/affiliation) to
    # this IdP's actual SAML attribute names (2.a.ii) — defaults to common
    # eduPerson/UK federation OIDs if not set; see DEFAULT_ATTRIBUTE_MAPPING.
    saml_attribute_mapping: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)

    def is_license_active(self) -> bool:
        return self.license_status == UniversityLicenseStatus.ACTIVE
