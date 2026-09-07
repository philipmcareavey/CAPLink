from datetime import date, datetime
from typing import Optional

from sqlalchemy import Date, DateTime, Float, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.models.enums import ContractStatus, MilestoneStatus, PaymentRail


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

    # Technical Implementation Plan 3.c.ii — set once, at contract creation,
    # from a hard rule (never a business/student choice) — see
    # app/services/payroll.py::determine_payment_rail.
    payment_rail: Mapped[PaymentRail] = mapped_column(default=PaymentRail.SELF_EMPLOYED)

    milestones: Mapped[list["Milestone"]] = relationship(back_populates="contract", cascade="all, delete-orphan")


class Milestone(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "milestones"

    contract_id: Mapped[str] = mapped_column(ForeignKey("contracts.id"), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    due_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    payment_amount_gbp: Mapped[float] = mapped_column(Float, nullable=False)
    status: Mapped[MilestoneStatus] = mapped_column(default=MilestoneStatus.PENDING)
    stripe_payment_intent_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    # Stripe's own PaymentIntent status string ("requires_capture",
    # "succeeded", "canceled", ...), stored verbatim rather than mapped onto
    # a parallel enum of our own — this is what the nightly reconciliation
    # job (3.b.iv, scripts/reconcile_payments.py) diffs against Stripe's
    # live ledger.
    stripe_payment_intent_status: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    authorized_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    captured_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    # Set once a PAYE-rail milestone's payment has been included in an
    # umbrella-provider payroll export (3.c.iv) — prevents double-export,
    # not a payment/workflow state in its own right.
    payroll_exported_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    contract: Mapped["Contract"] = relationship(back_populates="milestones")
