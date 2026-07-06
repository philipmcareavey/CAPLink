from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.models.enums import BusinessTrustTier, StudentBand, UserRole


# ---------- Registration ----------

class StudentRegister(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8)
    full_name: str
    university_slug: str          # which licensed institution they belong to
    degree_title: str
    band: StudentBand


class BusinessRegister(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8)
    full_name: str                # contact person
    company_name: str
    company_registration_number: Optional[str] = None
    industry: Optional[str] = None


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


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


class StudentProfileUpdate(BaseModel):
    degree_title: Optional[str] = None
    modules: Optional[List[str]] = None
    skills: Optional[List[str]] = None
    portfolio_urls: Optional[List[str]] = None
    hourly_rate_expectation_gbp: Optional[float] = None
    weekly_hours_available: Optional[int] = None


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
