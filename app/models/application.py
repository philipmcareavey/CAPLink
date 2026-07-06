from typing import Optional

from sqlalchemy import Float, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.models.enums import ApplicationStatus


class Application(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "applications"

    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), nullable=False)
    student_id: Mapped[str] = mapped_column(ForeignKey("student_profiles.id"), nullable=False)

    cover_note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    proposed_rate_gbp: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    status: Mapped[ApplicationStatus] = mapped_column(default=ApplicationStatus.SUBMITTED)

    # Snapshot of the match score at time of application — useful for the
    # recommendation engine's training data even if the student's profile
    # changes later.
    match_score_at_application: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    project: Mapped["Project"] = relationship(back_populates="applications")
