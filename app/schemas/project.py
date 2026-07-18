from typing import List, Optional

from pydantic import BaseModel, ConfigDict

from app.models.enums import ProjectCategory, ProjectStatus, StudentBand


class ProjectCreate(BaseModel):
    title: str
    description: str
    category: ProjectCategory
    required_skills: List[str] = []
    duration_label: str
    estimated_hours: Optional[int] = None
    hourly_rate_gbp: float
    is_remote: bool = True
    location_label: Optional[str] = None
    target_university_ids: List[str] = []
    target_bands: List[StudentBand] = []


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
