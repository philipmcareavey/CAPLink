"""
Student payroll rail (Technical Implementation Plan 3.c). Two genuinely
different steps live here:

1. `determine_payment_rail` — a real, enforced business rule (3.c.iii), not
   a stub. No external account needed for this half; it's pure logic.
2. Everything below it (3.c.i/3.c.iv) — a real umbrella/employer-of-record
   provider integration, which this codebase deliberately does NOT pick a
   specific vendor for. Unlike Stripe/Sentry/hCaptcha (where "which
   provider" was already decided and only the account was missing), no
   umbrella provider has been chosen for CAPLink yet — picking one is a
   real commercial/legal relationship (a contract with an actual
   employer-of-record company), not a technical decision this codebase can
   make on its own. Built as a clean, swappable abstraction instead (same
   shape as app/services/email.py/notifications.py's provider-agnostic
   stubs) so wiring in a real provider later means implementing
   `PayrollProvider`, not restructuring anything that calls it.
"""
import csv
import io
import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from app.models.contract import Contract, Milestone
from app.models.enums import PaymentRail
from app.models.user import StudentProfile

logger = logging.getLogger("caplink.payroll")


def determine_payment_rail(student: StudentProfile) -> PaymentRail:
    """Technical Implementation Plan 3.c.iii: a hard rule, never a
    business/student choice, and never overridable per-contract. A student
    is visa-restricted precisely when `visa_weekly_hour_cap` is set — this
    reuses that existing field (see app/models/user.py) rather than adding
    a second, potentially-inconsistent "is this student visa-restricted"
    flag. Called once, at contract creation (contracts.py::create_contract)
    — a contract's rail never changes after that, even if the student's
    visa status changes mid-contract (a genuinely new legal situation that
    needs a new contract, not a silently-mutated old one)."""
    if student.visa_weekly_hour_cap is not None:
        return PaymentRail.PAYE_UMBRELLA
    return PaymentRail.SELF_EMPLOYED


@dataclass
class PayrollLineItem:
    student_full_name: str
    student_email: str
    project_reference: str
    amount_gbp: float
    pay_period_end: datetime


class PayrollProvider(Protocol):
    """Technical Implementation Plan 3.c.i's real interface. A real
    implementation (once a provider is chosen) either calls that
    provider's API directly, or — many UK umbrella/EOR providers only
    offer file-based ingestion, not a live API — writes the same CSV
    `export_payroll_csv` below already produces to wherever that provider
    expects it (SFTP, an email attachment, a shared drive)."""

    def submit(self, line_items: list[PayrollLineItem]) -> None: ...


class LoggingPayrollProvider:
    """Placeholder implementation — logs instead of calling a real
    provider, same shape as email.py/notifications.py's stubs. Swap for a
    real provider's implementation of PayrollProvider once one is chosen;
    nothing calling `submit_payroll_batch` below needs to change."""

    def submit(self, line_items: list[PayrollLineItem]) -> None:
        for item in line_items:
            logger.info(
                "payroll_line_item",
                extra={
                    "student_email": item.student_email,
                    "project_reference": item.project_reference,
                    "amount_gbp": item.amount_gbp,
                },
            )


def export_payroll_csv(milestones: list[tuple[Milestone, Contract, StudentProfile]]) -> str:
    """Technical Implementation Plan 3.c.iv — "per-pay-period export of
    hours, rate, and project reference in the format the chosen umbrella
    provider requires." No provider is chosen yet, so this produces a
    generic, clearly-labelled CSV (project reference, student name/email,
    milestone description, amount) rather than guessing a specific
    provider's exact column format — that format is trivial to change once
    a real provider is under contract, but shouldn't be guessed at now."""
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(["project_reference", "student_full_name", "student_email", "milestone_description", "amount_gbp"])
    for milestone, contract, student in milestones:
        writer.writerow(
            [contract.project_id, student.user.full_name, student.user.email, milestone.description, milestone.payment_amount_gbp]
        )
    return buffer.getvalue()


def submit_payroll_batch(milestones: list[tuple[Milestone, Contract, StudentProfile]], provider: PayrollProvider) -> None:
    """Marks each milestone exported so a later run never double-submits
    it — callers should only pass milestones that are actually due for
    payroll (PAYE rail, captured, not yet exported)."""
    line_items = [
        PayrollLineItem(
            student_full_name=student.user.full_name,
            student_email=student.user.email,
            project_reference=contract.project_id,
            amount_gbp=milestone.payment_amount_gbp,
            pay_period_end=datetime.utcnow(),
        )
        for milestone, contract, student in milestones
    ]
    provider.submit(line_items)
    for milestone, _contract, _student in milestones:
        milestone.payroll_exported_at = datetime.utcnow()
