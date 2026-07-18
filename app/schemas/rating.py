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


class RatingHistoryEntry(BaseModel):
    """Full rating history, both directions — unlike /pending (given-only,
    unreleased-only). A rating I received stays hidden (score/sub_scores
    null) until is_released, mirroring submit_rating's blind-until-both-
    submit release logic; a rating I gave is always visible to me."""
    id: str
    contract_id: str
    counterpart_user_id: str
    direction: str  # "given" | "received"
    is_released: bool
    overall_score: Optional[float]
    sub_scores: Optional[dict]
    visibility: RatingVisibility
