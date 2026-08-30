from datetime import date
from typing import Optional

from sqlalchemy import Date, Float, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.models.enums import ContractStatus, MilestoneStatus


class Contract(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "contracts"

    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), nullable=False)
    application_id: Mapped[str] = mapped_column(ForeignKey("applications.id"), nullable=False)
    student_id: Mapped[str] = mapped_column(ForeignKey("student_profiles.id"), nullable=False)
    business_id: Mapped[str] = mapped_column(ForeignKey("business_profiles.id"), nullable=False)

    terms_document_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    ip_assignment_accepted: Mapped[bool] = mapped_column(default=False)
    nda_accepted: Mapped[bool] = mapped_column(default=False)

    status: Mapped[ContractStatus] = mapped_column(default=ContractStatus.ACTIVE)

    milestones: Mapped[list["Milestone"]] = relationship(back_populates="contract", cascade="all, delete-orphan")


class Milestone(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "milestones"

    contract_id: Mapped[str] = mapped_column(ForeignKey("contracts.id"), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    due_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    payment_amount_gbp: Mapped[float] = mapped_column(Float, nullable=False)
    status: Mapped[MilestoneStatus] = mapped_column(default=MilestoneStatus.PENDING)
    stripe_payment_intent_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    contract: Mapped["Contract"] = relationship(back_populates="milestones")
