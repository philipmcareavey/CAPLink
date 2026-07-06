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


class ProjectApplicantEntry(BaseModel):
    """What a business sees when reviewing who has actually applied to one
    of its projects — distinct from the shortlist, which is a candidate
    search across everyone eligible whether or not they've applied."""
    application_id: str
    student_id: str
    full_name: str
    degree_title: str
    cover_note: Optional[str]
    proposed_rate_gbp: Optional[float]
    status: ApplicationStatus
    match_score_at_application: Optional[float]
