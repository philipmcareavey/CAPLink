from datetime import date
from typing import List, Optional, TYPE_CHECKING

from sqlalchemy import Date, Float, String
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

    def is_license_active(self) -> bool:
        return self.license_status == UniversityLicenseStatus.ACTIVE
