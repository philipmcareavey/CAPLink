from typing import List, Optional

from pydantic import BaseModel, ConfigDict

from app.models.enums import AgreementStatus, ProjectCategory, StudentBand


class AgreementCreate(BaseModel):
    """A business requests access to a university's students."""
    business_id: str


class AgreementDecision(BaseModel):
    """A university admin approves/rejects/edits a business's access."""
    status: AgreementStatus
    allowed_bands: List[StudentBand] = []
    allowed_categories: List[ProjectCategory] = []
    max_active_projects: Optional[int] = None
    requires_university_project_review: bool = False
    university_notes: Optional[str] = None


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
