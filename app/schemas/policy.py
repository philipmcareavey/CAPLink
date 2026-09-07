from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import AgreementStatus, ProjectCategory, StudentBand


class AgreementCreate(BaseModel):
    """A business requests access to a university's students."""
    business_id: str = Field(max_length=36)


class AgreementDecision(BaseModel):
    """A university admin approves/rejects/edits a business's access."""
    status: AgreementStatus
    allowed_bands: List[StudentBand] = Field(default=[], max_length=20)
    allowed_categories: List[ProjectCategory] = Field(default=[], max_length=50)
    max_active_projects: Optional[int] = Field(default=None, ge=0, le=100_000)
    requires_university_project_review: bool = False
    university_notes: Optional[str] = Field(default=None, max_length=5_000)


class AgreementOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    university_id: str
    business_id: str
    status: AgreementStatus
    allowed_bands: List[str]
    allowed_categories: List[str]
    max_active_projects: Optional[int]
    requires_university_project_review: bool
