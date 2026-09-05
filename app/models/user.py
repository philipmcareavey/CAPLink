from datetime import datetime
from typing import List, Optional, TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, JSON, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.models.enums import BusinessTrustTier, StudentBand, UserRole

if TYPE_CHECKING:
    from app.models.device import Device


class User(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "users"

    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[UserRole] = mapped_column(nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_email_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)

    # A student belongs to exactly one licensed university (their institution).
    # University admins also belong to the university they administer.
    university_id: Mapped[Optional[str]] = mapped_column(ForeignKey("universities.id"), nullable=True)

    # --- Auth hardening (Technical Implementation Plan 2.a) ---

    # 2.a.ii — account lockout / exponential backoff. Reset to 0/None on any
    # successful login; incremented on a wrong password. See
    # app/services/account_lockout.py for the actual backoff calculation.
    failed_login_attempts: Mapped[int] = mapped_column(Integer, default=0)
    locked_until: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    # 2.a.iii — real (confirmation-link) email verification, replacing the
    # old domain-match-only check. Cleared once used; a fresh
    # register/resend overwrites both together, so an old link can never
    # verify a newer registration attempt.
    email_verification_token: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    email_verification_token_expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    # 2.a.iv — TOTP MFA, required for university_admin/platform_admin once
    # enabled. totp_secret is written on /mfa/setup but only takes effect
    # (blocks login without a code) once totp_enabled flips true on
    # /mfa/enable — see app/services/mfa.py. Backup codes are stored
    # bcrypt-hashed, never in plaintext, and consumed one-time on use.
    totp_secret: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    totp_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    mfa_backup_codes: Mapped[list] = mapped_column(JSON, default=list)

    student_profile: Mapped[Optional["StudentProfile"]] = relationship(
        back_populates="user", uselist=False, cascade="all, delete-orphan"
    )
    business_profile: Mapped[Optional["BusinessProfile"]] = relationship(
        back_populates="user", uselist=False, cascade="all, delete-orphan"
    )
    devices: Mapped[List["Device"]] = relationship(back_populates="user", cascade="all, delete-orphan")


class StudentProfile(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "student_profiles"

    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), unique=True, nullable=False)
    university_id: Mapped[str] = mapped_column(ForeignKey("universities.id"), nullable=False)

    degree_title: Mapped[str] = mapped_column(String(255), nullable=False)
    band: Mapped[StudentBand] = mapped_column(nullable=False)  # drives safeguarding access rules
    modules: Mapped[list] = mapped_column(JSON, default=list)        # ["Statistics II", "Machine Learning"]
    skills: Mapped[list] = mapped_column(JSON, default=list)         # ["Python", "SQL"]
    portfolio_urls: Mapped[list] = mapped_column(JSON, default=list)
    hourly_rate_expectation_gbp: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    weekly_hours_available: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    right_to_work_confirmed: Mapped[bool] = mapped_column(Boolean, default=False)
    visa_weekly_hour_cap: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)  # enforced if set
    is_id_verified: Mapped[bool] = mapped_column(Boolean, default=False)

    # Reputation (denormalised for fast reads; recomputed by rating service)
    average_rating: Mapped[float] = mapped_column(Float, default=0.0)
    completed_projects_count: Mapped[int] = mapped_column(Integer, default=0)
    on_time_rate: Mapped[float] = mapped_column(Float, default=0.0)

    user: Mapped["User"] = relationship(back_populates="student_profile")


class BusinessProfile(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "business_profiles"

    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), unique=True, nullable=False)

    company_name: Mapped[str] = mapped_column(String(255), nullable=False)
    company_registration_number: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    industry: Mapped[Optional[str]] = mapped_column(String(150), nullable=True)
    company_size: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)  # "1-10", "11-50", ...
    website: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    description: Mapped[Optional[str]] = mapped_column(String(2000), nullable=True)

    # Location — geocoded from postcode, powers "local businesses within
    # X miles of campus" search. Optional: a fully-remote business can
    # simply never set this and will never appear in radius results.
    postcode: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    latitude: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    longitude: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    # Global trust tier — separate from the PER-UNIVERSITY agreement status,
    # which governs whether this business can actually reach that university's students.
    global_trust_tier: Mapped[BusinessTrustTier] = mapped_column(default=BusinessTrustTier.UNVERIFIED)
    is_registration_verified: Mapped[bool] = mapped_column(Boolean, default=False)

    average_rating: Mapped[float] = mapped_column(Float, default=0.0)
    completed_projects_count: Mapped[int] = mapped_column(Integer, default=0)
    payment_promptness_score: Mapped[float] = mapped_column(Float, default=0.0)

    user: Mapped["User"] = relationship(back_populates="business_profile")
