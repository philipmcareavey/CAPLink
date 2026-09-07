from typing import Annotated, List, Optional

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import ProjectCategory, ProjectStatus, StudentBand

ShortListItem = Annotated[str, Field(min_length=1, max_length=100)]


class ProjectCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    description: str = Field(min_length=1, max_length=10_000)
    category: ProjectCategory
    required_skills: List[ShortListItem] = Field(default=[], max_length=50)
    duration_label: str = Field(min_length=1, max_length=100)
    estimated_hours: Optional[int] = Field(default=None, ge=0, le=100_000)
    hourly_rate_gbp: float = Field(ge=0, le=10_000)
    is_remote: bool = True
    location_label: Optional[str] = Field(default=None, max_length=200)
    target_university_ids: List[Annotated[str, Field(max_length=36)]] = Field(default=[], max_length=200)
    target_bands: List[StudentBand] = Field(default=[], max_length=20)


class ProjectOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    business_id: str
    title: str
    description: str
    category: ProjectCategory
    required_skills: List[str]
    duration_label: str
    estimated_hours: Optional[int]
    hourly_rate_gbp: float
    is_remote: bool
    location_label: Optional[str]
    status: ProjectStatus


class ProjectWithMatch(ProjectOut):
    """What a student sees in their suggested feed — score + human-readable reasons."""
    match_score: float
    match_reasons: List[str]


class MatchFactorOut(BaseModel):
    name: str
    raw_score: float
    weight: float
    contribution: float
    detail: str


class MatchExplanationOut(BaseModel):
    """Full breakdown behind a match score — powers a 'why this match?' detail
    view, and doubles as a debugging tool when tuning engine weights."""
    score: float
    algorithm_version: str
    reasons: List[str]
    breakdown: List[MatchFactorOut]
