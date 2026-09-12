"""Technical Implementation Plan 3.d — Financial Reporting. Two real
aggregation reports over data that already exists (Contract/Milestone),
same "pure aggregation, no new columns" shape as
app/services/employability_report.py.

"Authorized, pending capture" below means a milestone whose card
authorization is still held but not yet captured — status PENDING (just
created) or SUBMITTED (student has submitted the deliverable, awaiting the
business's approve-and-pay) — see app/api/v1/endpoints/contracts.py's
status transitions. REJECTED/AUTHORIZATION_FAILED/REFUNDED/DISPUTED
milestones never became real spend or revenue and are excluded from both
reports entirely, not counted as zero.
"""
from collections import defaultdict
from dataclasses import dataclass, field

from sqlalchemy.orm import Session

from app.models.contract import Contract, Milestone
from app.models.enums import MilestoneStatus
from app.models.project import Project
from app.services.stripe_payments import calculate_platform_fee_gbp

_PENDING_CAPTURE_STATUSES = (MilestoneStatus.PENDING, MilestoneStatus.SUBMITTED)


@dataclass
class ProjectSpend:
    project_id: str
    project_title: str
    paid_gbp: float
    pending_capture_gbp: float


@dataclass
class BusinessSpendReport:
    total_paid_gbp: float
    total_pending_capture_gbp: float
    monthly_paid_gbp: dict[str, float]
    by_project: list[ProjectSpend]


def build_business_spend_report(db: Session, business_id: str) -> BusinessSpendReport:
    contracts = db.query(Contract).filter(Contract.business_id == business_id).all()
    contract_ids = [c.id for c in contracts]
    milestones = db.query(Milestone).filter(Milestone.contract_id.in_(contract_ids)).all() if contract_ids else []
    project_ids = {c.project_id for c in contracts}
    projects_by_id = {p.id: p for p in db.query(Project).filter(Project.id.in_(project_ids)).all()} if project_ids else {}

    project_id_by_contract = {c.id: c.project_id for c in contracts}
    totals_by_project: dict[str, dict[str, float]] = defaultdict(lambda: {"paid": 0.0, "pending": 0.0})
    monthly_paid: dict[str, float] = defaultdict(float)
    total_paid = 0.0
    total_pending = 0.0

    for milestone in milestones:
        project_id = project_id_by_contract[milestone.contract_id]
        if milestone.status == MilestoneStatus.PAID:
            total_paid += milestone.payment_amount_gbp
            totals_by_project[project_id]["paid"] += milestone.payment_amount_gbp
            if milestone.captured_at is not None:
                monthly_paid[milestone.captured_at.strftime("%Y-%m")] += milestone.payment_amount_gbp
        elif milestone.status in _PENDING_CAPTURE_STATUSES:
            total_pending += milestone.payment_amount_gbp
            totals_by_project[project_id]["pending"] += milestone.payment_amount_gbp

    by_project = [
        ProjectSpend(
            project_id=project_id,
            project_title=projects_by_id[project_id].title if project_id in projects_by_id else "Unknown project",
            paid_gbp=round(totals["paid"], 2),
            pending_capture_gbp=round(totals["pending"], 2),
        )
        for project_id, totals in totals_by_project.items()
    ]
    by_project.sort(key=lambda p: p.paid_gbp, reverse=True)

    return BusinessSpendReport(
        total_paid_gbp=round(total_paid, 2),
        total_pending_capture_gbp=round(total_pending, 2),
        monthly_paid_gbp={month: round(amount, 2) for month, amount in sorted(monthly_paid.items())},
        by_project=by_project,
    )


@dataclass
class PlatformRevenueReport:
    gross_payment_volume_gbp: float
    platform_fee_revenue_gbp: float
    monthly_platform_fee_revenue_gbp: dict[str, float]
    # Technical Implementation Plan 3.d.ii's own wording: "with a placeholder
    # line for license revenue once that's tracked" — CAPLink's university
    # licensing is sold/invoiced outside this codebase today (no
    # subscription/billing model exists anywhere in app/ to derive a real
    # figure from), so this is honestly zero rather than a guessed number,
    # not an omission.
    license_revenue_gbp: float = field(default=0.0)


def build_platform_revenue_report(db: Session) -> PlatformRevenueReport:
    paid_milestones = db.query(Milestone).filter(Milestone.status == MilestoneStatus.PAID).all()

    gross_volume = 0.0
    fee_revenue = 0.0
    monthly_fees: dict[str, float] = defaultdict(float)

    for milestone in paid_milestones:
        gross_volume += milestone.payment_amount_gbp
        fee = calculate_platform_fee_gbp(milestone.payment_amount_gbp)
        fee_revenue += fee
        if milestone.captured_at is not None:
            monthly_fees[milestone.captured_at.strftime("%Y-%m")] += fee

    return PlatformRevenueReport(
        gross_payment_volume_gbp=round(gross_volume, 2),
        platform_fee_revenue_gbp=round(fee_revenue, 2),
        monthly_platform_fee_revenue_gbp={month: round(amount, 2) for month, amount in sorted(monthly_fees.items())},
    )
