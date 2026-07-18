from typing import Optional

from pydantic import BaseModel, ConfigDict

from app.models.enums import ApplicationStatus


class ApplicationCreate(BaseModel):
    project_id: str
    cover_note: Optional[str] = None
    proposed_rate_gbp: Optional[float] = None


class ApplicationStatusUpdate(BaseModel):
    status: ApplicationStatus


class ApplicationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    project_id: str
    student_id: str
    cover_note: Optional[str]
    proposed_rate_gbp: Optional[float]
    status: ApplicationStatus
    match_score_at_application: Optional[float]


class StudentShortlistEntry(BaseModel):
    """What a business sees when browsing candidates for one of its projects."""
    student_id: str
    full_name: str
    degree_title: str
    university_name: str
    average_rating: float
    completed_projects_count: int
    match_score: float
    match_reasons: list[str]


class ApplicantOut(BaseModel):
    """What a business sees for an actual applicant to one of its projects —
    distinct from StudentShortlistEntry (which ranks candidates, applied or
    not). Includes student_user_id so the UI can act on this specific
    person (message them, create a contract from application_id)."""
    application_id: str
    student_id: str
    student_user_id: str
    full_name: str
    degree_title: str
    status: ApplicationStatus
    cover_note: Optional[str]
    proposed_rate_gbp: Optional[float]
    match_score_at_application: Optional[float]
