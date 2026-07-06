from typing import Optional

from sqlalchemy import Float, ForeignKey, JSON, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base_class import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.models.enums import RatingVisibility


class Rating(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "ratings"

    contract_id: Mapped[str] = mapped_column(ForeignKey("contracts.id"), nullable=False)
    rater_user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False)
    ratee_user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False)

    overall_score: Mapped[float] = mapped_column(Float, nullable=False)  # 1.0 - 5.0
    # e.g. {"communication": 5, "quality": 4, "reliability": 5, "professionalism": 5}
    # or   {"clarity_of_brief": 5, "payment_promptness": 5, "respectful_treatment": 4}
    sub_scores: Mapped[dict] = mapped_column(JSON, default=dict)

    private_comment: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    visibility: Mapped[RatingVisibility] = mapped_column(default=RatingVisibility.PUBLIC)

    # Ratings stay hidden from the other party until both sides submit,
    # or the response window (e.g. 14 days) lapses. Set by the service layer.
    is_released: Mapped[bool] = mapped_column(default=False)
    is_flagged_for_review: Mapped[bool] = mapped_column(default=False)
