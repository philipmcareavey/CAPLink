from typing import Optional, TYPE_CHECKING

from sqlalchemy import ForeignKey, JSON, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.models.enums import AgreementStatus

if TYPE_CHECKING:
    from app.models.university import University


class UniversityBusinessAgreement(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """
    This is the safeguarding + relevance control at the heart of the licensing
    model. A business has NO visibility of a university's students until an
    agreement exists and is approved — and even then, only within the bands
    and categories the university has explicitly allowed.

    Example: University of Manchester might approve 'DataCraft Analytics'
    for [YEAR_2, YEAR_3, YEAR_4_PLUS, POSTGRAD_TAUGHT] and category
    [DATA_ANALYTICS, RESEARCH] only — so first-years never appear in
    DataCraft's shortlist, and DataCraft can't post, say, a sales role.
    """
    __tablename__ = "university_business_agreements"

    university_id: Mapped[str] = mapped_column(ForeignKey("universities.id"), nullable=False)
    business_id: Mapped[str] = mapped_column(ForeignKey("business_profiles.id"), nullable=False)

    status: Mapped[AgreementStatus] = mapped_column(default=AgreementStatus.PENDING)

    # Stored as JSON lists of enum values (StudentBand / ProjectCategory strings)
    allowed_bands: Mapped[list] = mapped_column(JSON, default=list)
    allowed_categories: Mapped[list] = mapped_column(JSON, default=list)

    max_active_projects: Mapped[Optional[int]] = mapped_column(default=None)  # None = unlimited
    requires_university_project_review: Mapped[bool] = mapped_column(default=False)  # extra moderation gate

    university_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # internal, not shown to business
    reviewed_by_admin_id: Mapped[Optional[str]] = mapped_column(ForeignKey("users.id"), nullable=True)

    university: Mapped["University"] = relationship(back_populates="business_agreements")
