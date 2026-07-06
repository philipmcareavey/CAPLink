import enum


class UserRole(str, enum.Enum):
    STUDENT = "student"
    BUSINESS = "business"
    UNIVERSITY_ADMIN = "university_admin"   # careers service staff at a licensed university
    PLATFORM_ADMIN = "platform_admin"       # CAPLink internal staff


class UniversityLicenseTier(str, enum.Enum):
    TRIAL = "trial"
    STANDARD = "standard"
    ENTERPRISE = "enterprise"


class UniversityLicenseStatus(str, enum.Enum):
    PENDING = "pending"
    ACTIVE = "active"
    SUSPENDED = "suspended"
    EXPIRED = "expired"


class StudentBand(str, enum.Enum):
    """
    Safeguarding/relevance banding. Universities restrict which businesses
    can see/contact/hire students in each band — e.g. first-years might be
    limited to verified, education-partner businesses only, while final
    years and postgrads can access the full open marketplace.
    """
    FOUNDATION = "foundation_year"
    YEAR_1 = "year_1"
    YEAR_2 = "year_2"
    YEAR_3 = "year_3"
    YEAR_4_PLUS = "year_4_plus"
    POSTGRAD_TAUGHT = "postgrad_taught"
    POSTGRAD_RESEARCH = "postgrad_research"
    RECENT_ALUMNI = "recent_alumni"  # within platform-defined grad window


class BusinessTrustTier(str, enum.Enum):
    """Escalating trust levels a business can hold, globally and per-university."""
    UNVERIFIED = "unverified"
    ID_VERIFIED = "id_verified"              # company registration confirmed
    UNIVERSITY_APPROVED = "university_approved"  # explicitly approved by >=1 university
    STRATEGIC_PARTNER = "strategic_partner"      # formal agreement, e.g. sponsors grad schemes


class AgreementStatus(str, enum.Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    SUSPENDED = "suspended"


class ProjectCategory(str, enum.Enum):
    DATA_ANALYTICS = "data_analytics"
    SOFTWARE_ENGINEERING = "software_engineering"
    MARKETING = "marketing"
    DESIGN = "design"
    RESEARCH = "research"
    FINANCE = "finance"
    OPERATIONS = "operations"
    OTHER = "other"


class ProjectStatus(str, enum.Enum):
    DRAFT = "draft"
    PENDING_REVIEW = "pending_review"   # awaiting platform/university moderation
    OPEN = "open"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class ApplicationStatus(str, enum.Enum):
    SUBMITTED = "submitted"
    SHORTLISTED = "shortlisted"
    INTERVIEWING = "interviewing"
    OFFERED = "offered"
    ACCEPTED = "accepted"
    DECLINED = "declined"
    REJECTED = "rejected"
    WITHDRAWN = "withdrawn"


class ContractStatus(str, enum.Enum):
    ACTIVE = "active"
    COMPLETED = "completed"
    TERMINATED = "terminated"
    DISPUTED = "disputed"


class MilestoneStatus(str, enum.Enum):
    PENDING = "pending"
    SUBMITTED = "submitted"
    APPROVED = "approved"
    PAID = "paid"
    DISPUTED = "disputed"


class RatingVisibility(str, enum.Enum):
    PUBLIC = "public"
    PLATFORM_ONLY = "platform_only"


class DevicePlatform(str, enum.Enum):
    IOS = "ios"
    ANDROID = "android"
    WEB = "web"
