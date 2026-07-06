from typing import Optional

from sqlalchemy import Float, ForeignKey, JSON, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base_class import Base, TimestampMixin, UUIDPrimaryKeyMixin


class RecommendationLog(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """
    Every recommendation shown to any user is logged here: what was shown,
    why (as human-readable reason chips), the raw score, and what the user
    did next. This is the training data for every future improvement to the
    matching engine — build it from day one even while the engine itself is
    simple rules-based scoring.
    """
    __tablename__ = "recommendation_logs"

    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False)
    entity_type: Mapped[str] = mapped_column(String(50), nullable=False)  # "project" | "student"
    entity_id: Mapped[str] = mapped_column(String(36), nullable=False)

    score: Mapped[float] = mapped_column(Float, nullable=False)
    reasons: Mapped[list] = mapped_column(JSON, default=list)  # ["Python match", "Available this week"]
    algorithm_version: Mapped[str] = mapped_column(String(50), default="rules_v1")

    action_taken: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)  # "applied" | "dismissed" | "messaged" | None
