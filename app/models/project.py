from typing import Optional, TYPE_CHECKING

from sqlalchemy import Float, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.models.enums import ProjectCategory, ProjectStatus

if TYPE_CHECKING:
    from app.models.application import Application


class Project(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "projects"

    business_id: Mapped[str] = mapped_column(ForeignKey("business_profiles.id"), nullable=False)

    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    category: Mapped[ProjectCategory] = mapped_column(nullable=False)
    required_skills: Mapped[list] = mapped_column(JSON, default=list)

    duration_label: Mapped[str] = mapped_column(String(100), nullable=False)  # "1-2 weeks", "Ongoing"
    estimated_hours: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    hourly_rate_gbp: Mapped[float] = mapped_column(Float, nullable=False)
    is_remote: Mapped[bool] = mapped_column(default=True)
    location_label: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # Safeguarding: which universities this project is even visible to, and which
    # student bands within them. Cross-checked at query time against the
    # UniversityBusinessAgreement for the business that owns this project.
    target_university_ids: Mapped[list] = mapped_column(JSON, default=list)
    target_bands: Mapped[list] = mapped_column(JSON, default=list)

    status: Mapped[ProjectStatus] = mapped_column(default=ProjectStatus.DRAFT)

    applications: Mapped[list["Application"]] = relationship(back_populates="project", cascade="all, delete-orphan")
