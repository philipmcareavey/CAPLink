from typing import Optional

from pydantic import BaseModel, Field


class LocalBusinessResult(BaseModel):
    business_id: str
    company_name: str
    industry: Optional[str]
    postcode: Optional[str]
    distance_miles: float
    degree_relevance_score: float = Field(description="0-1, from the same degree-relevance scorer used in project matching")
    degree_relevance_label: str
    approved_categories: list[str]
    average_rating: float
    completed_projects_count: int


class LocalSearchMeta(BaseModel):
    campus_name: str
    campus_postcode: Optional[str]
    radius_miles: float
    total_results: int
