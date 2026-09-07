from datetime import datetime
from typing import Annotated, List, Optional

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.models.enums import BusinessTrustTier, StudentBand, UserRole

ShortListItem = Annotated[str, Field(min_length=1, max_length=100)]


# ---------- Registration ----------

# Technical Implementation Plan 2.c.ii — every free-text field below carries
# an explicit max_length. Pydantic rejects an oversized payload before it
# ever reaches a query or gets stored, rather than relying on the database
# column (which, for SQLite/Postgres TEXT/VARCHAR here, wouldn't reject it
# at all) to be the only backstop.
NAME_MAX_LENGTH = 200
SLUG_MAX_LENGTH = 100
SHORT_TEXT_MAX_LENGTH = 500
PASSWORD_MAX_LENGTH = 128  # bcrypt itself silently truncates past 72 bytes; this just caps the request body


class StudentRegister(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=PASSWORD_MAX_LENGTH)
    full_name: str = Field(min_length=1, max_length=NAME_MAX_LENGTH)
    university_slug: str = Field(min_length=1, max_length=SLUG_MAX_LENGTH)  # which licensed institution they belong to
    degree_title: str = Field(min_length=1, max_length=NAME_MAX_LENGTH)
    band: StudentBand
    captcha_token: Optional[str] = Field(default=None, max_length=SHORT_TEXT_MAX_LENGTH)
    # Technical Implementation Plan 7.b.i — explicit opt-in, not a
    # pre-ticked default and not inferred from registering at all. `bool`
    # rather than `Optional[bool] = False` deliberately: a client that
    # forgets to send this field gets a 422, not a silent False, since this
    # is a genuine consent requirement, not an ordinary optional setting.
    data_sharing_consent: bool = Field(
        description="Must be true — explicit consent to share engagement/outcome data with the student's university"
    )


class BusinessRegister(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=PASSWORD_MAX_LENGTH)
    full_name: str = Field(min_length=1, max_length=NAME_MAX_LENGTH)  # contact person
    company_name: str = Field(min_length=1, max_length=NAME_MAX_LENGTH)
    company_registration_number: Optional[str] = Field(default=None, max_length=50)
    industry: Optional[str] = Field(default=None, max_length=NAME_MAX_LENGTH)
    captcha_token: Optional[str] = Field(default=None, max_length=SHORT_TEXT_MAX_LENGTH)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(max_length=PASSWORD_MAX_LENGTH)


class RegistrationResult(BaseModel):
    """Registration no longer returns tokens directly (2.a.iii) — a new
    account must verify its email via the confirmation link before it can
    log in at all."""
    message: str = "Registration successful. Check your email to verify your account before logging in."


class ChangePasswordRequest(BaseModel):
    current_password: str = Field(max_length=PASSWORD_MAX_LENGTH)
    new_password: str = Field(min_length=8, max_length=PASSWORD_MAX_LENGTH)


class ResendVerificationRequest(BaseModel):
    email: EmailStr


# ---------- Read models ----------

class StudentProfileOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    degree_title: str
    band: StudentBand
    modules: List[str]
    skills: List[str]
    portfolio_urls: List[str]
    hourly_rate_expectation_gbp: Optional[float]
    weekly_hours_available: Optional[int]
    is_id_verified: bool
    average_rating: float
    completed_projects_count: int
    on_time_rate: float
    data_sharing_consent_at: Optional[datetime]


class StudentProfileUpdate(BaseModel):
    degree_title: Optional[str] = Field(default=None, min_length=1, max_length=NAME_MAX_LENGTH)
    modules: Optional[List[ShortListItem]] = Field(default=None, max_length=100)
    skills: Optional[List[ShortListItem]] = Field(default=None, max_length=100)
    portfolio_urls: Optional[List[Annotated[str, Field(max_length=500)]]] = Field(default=None, max_length=20)
    hourly_rate_expectation_gbp: Optional[float] = Field(default=None, ge=0, le=10_000)
    weekly_hours_available: Optional[int] = Field(default=None, ge=0, le=168)


class BusinessProfileOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    company_name: str
    industry: Optional[str]
    company_size: Optional[str]
    website: Optional[str]
    description: Optional[str]
    global_trust_tier: BusinessTrustTier
    is_registration_verified: bool
    average_rating: float
    completed_projects_count: int
    postcode: Optional[str]
    latitude: Optional[float]
    longitude: Optional[float]


class BusinessProfileUpdate(BaseModel):
    company_name: Optional[str] = Field(default=None, min_length=1, max_length=NAME_MAX_LENGTH)
    industry: Optional[str] = Field(default=None, max_length=NAME_MAX_LENGTH)
    company_size: Optional[str] = Field(default=None, max_length=50)
    website: Optional[str] = Field(default=None, max_length=500)
    description: Optional[str] = Field(default=None, max_length=5_000)
    postcode: Optional[str] = Field(default=None, max_length=20)  # setting/changing this triggers re-geocoding server-side


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    email: EmailStr
    full_name: str
    role: UserRole
    is_active: bool
    is_email_verified: bool
    university_id: Optional[str]
    student_profile: Optional[StudentProfileOut] = None
    business_profile: Optional[BusinessProfileOut] = None
