"""Technical Implementation Plan 5.d.iii — employability outcomes reporting
for a university's careers team: how many of their students engaged with
the platform, got hired, completed their work, and how much they actually
earned, broken down by band. Pure aggregation over data that already
exists (Application/Contract/Milestone/Rating) — no new columns needed.

Contract.status is a real field, but nothing in this codebase ever
transitions it to ContractStatus.COMPLETED (grep confirms no assignment
exists anywhere) — a contract's completion has to be derived instead. A
contract counts as completed here once every one of its milestones has
actually been paid, which is a signal this project genuinely maintains,
rather than one it doesn't.
"""
from collections import defaultdict
from dataclasses import dataclass, field

from sqlalchemy.orm import Session

from app.models.application import Application
from app.models.contract import Contract, Milestone
from app.models.enums import MilestoneStatus, StudentBand
from app.models.rating import Rating
from app.models.user import StudentProfile


@dataclass
class BandOutcome:
    band: StudentBand
    total_students: int
    applied_students: int
    hired_students: int
    completed_students: int
    earnings_gbp: float


@dataclass
class EmployabilityReport:
    total_students: int
    applied_students: int
    hired_students: int
    completed_students: int
    total_earnings_gbp: float
    average_student_rating: float | None
    rated_engagements: int
    band_breakdown: list[BandOutcome] = field(default_factory=list)


def build_employability_report(db: Session, university_id: str) -> EmployabilityReport:
    students = db.query(StudentProfile).filter(StudentProfile.university_id == university_id).all()
    if not students:
        return EmployabilityReport(0, 0, 0, 0, 0.0, None, 0, [])

    student_ids = [s.id for s in students]
    applications = db.query(Application).filter(Application.student_id.in_(student_ids)).all()
    contracts = db.query(Contract).filter(Contract.student_id.in_(student_ids)).all()
    contract_ids = [c.id for c in contracts]
    milestones = db.query(Milestone).filter(Milestone.contract_id.in_(contract_ids)).all() if contract_ids else []

    applied_student_ids = {a.student_id for a in applications}
    hired_student_ids = {c.student_id for c in contracts}

    contract_by_id = {c.id: c for c in contracts}
    milestones_by_contract: dict[str, list[Milestone]] = defaultdict(list)
    for m in milestones:
        milestones_by_contract[m.contract_id].append(m)

    completed_student_ids = {
        c.student_id
        for c in contracts
        if milestones_by_contract[c.id]
        and all(m.status == MilestoneStatus.PAID for m in milestones_by_contract[c.id])
    }

    earnings_by_student: dict[str, float] = defaultdict(float)
    for m in milestones:
        if m.status == MilestoneStatus.PAID:
            earnings_by_student[contract_by_id[m.contract_id].student_id] += m.payment_amount_gbp

    student_user_ids = [s.user_id for s in students]
    ratings = db.query(Rating).filter(Rating.ratee_user_id.in_(student_user_ids), Rating.is_released.is_(True)).all()
    average_rating = round(sum(r.overall_score for r in ratings) / len(ratings), 2) if ratings else None

    students_by_band: dict[StudentBand, list[StudentProfile]] = defaultdict(list)
    for s in students:
        students_by_band[s.band].append(s)

    band_breakdown = []
    for band in StudentBand:
        band_students = students_by_band.get(band)
        if not band_students:
            continue
        band_ids = {s.id for s in band_students}
        band_breakdown.append(
            BandOutcome(
                band=band,
                total_students=len(band_students),
                applied_students=len(applied_student_ids & band_ids),
                hired_students=len(hired_student_ids & band_ids),
                completed_students=len(completed_student_ids & band_ids),
                earnings_gbp=round(sum(earnings_by_student[sid] for sid in band_ids), 2),
            )
        )

    return EmployabilityReport(
        total_students=len(students),
        applied_students=len(applied_student_ids),
        hired_students=len(hired_student_ids),
        completed_students=len(completed_student_ids),
        total_earnings_gbp=round(sum(earnings_by_student.values()), 2),
        average_student_rating=average_rating,
        rated_engagements=len(ratings),
        band_breakdown=band_breakdown,
    )
