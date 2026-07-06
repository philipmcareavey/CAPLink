from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import RatingVisibility


class RatingCreate(BaseModel):
    contract_id: str
    overall_score: float = Field(ge=1.0, le=5.0)
    sub_scores: dict = {}
    private_comment: Optional[str] = None
    visibility: RatingVisibility = RatingVisibility.PUBLIC


class RatingOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    contract_id: str
    rater_user_id: str
    ratee_user_id: str
    overall_score: float
    sub_scores: dict
    visibility: RatingVisibility
    is_released: bool
