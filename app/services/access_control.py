"""
Access control / safeguarding service.

This is the single choke point every student <-> business interaction must
pass through: viewing a profile, appearing in a shortlist, applying to a
project, sending a message, or signing a contract. Centralising it here
means the rule is enforced consistently everywhere, instead of being
re-implemented (and potentially forgotten) in each endpoint.

Rule of thumb: a business has NO access to ANY student at a university until
an APPROVED UniversityBusinessAgreement exists, and even then only within
the bands/categories that agreement explicitly lists.
"""
from dataclasses import dataclass
from typing import Optional

from sqlalchemy.orm import Session

from app.models.enums import AgreementStatus
from app.models.policy import UniversityBusinessAgreement
from app.models.project import Project
from app.models.user import BusinessProfile, StudentProfile


@dataclass
class AccessDecision:
    allowed: bool
    reason: str


def get_agreement(
    db: Session, university_id: str, business_id: str
) -> Optional[UniversityBusinessAgreement]:
    return (
        db.query(UniversityBusinessAgreement)
        .filter(
            UniversityBusinessAgreement.university_id == university_id,
            UniversityBusinessAgreement.business_id == business_id,
        )
        .first()
    )


def can_business_access_student(
    db: Session, business: BusinessProfile, student: StudentProfile
) -> AccessDecision:
    agreement = get_agreement(db, student.university_id, business.id)

    if agreement is None:
        return AccessDecision(False, "No partnership agreement exists between this business and the student's university.")

    if agreement.status != AgreementStatus.APPROVED:
        return AccessDecision(False, f"Partnership agreement status is '{agreement.status.value}', not approved.")

    if student.band.value not in agreement.allowed_bands:
        return AccessDecision(
            False,
            f"This business is not approved to access students in band '{student.band.value}' at this university.",
        )

    return AccessDecision(True, "Access permitted under approved university agreement.")


def can_business_post_category_for_university(
    db: Session, business: BusinessProfile, university_id: str, category_value: str
) -> AccessDecision:
    agreement = get_agreement(db, university_id, business.id)

    if agreement is None or agreement.status != AgreementStatus.APPROVED:
        return AccessDecision(False, "No approved agreement with this university.")

    if category_value not in agreement.allowed_categories:
        return AccessDecision(
            False, f"This business is not approved to post '{category_value}' projects at this university."
        )

    return AccessDecision(True, "Category permitted under approved university agreement.")


def filter_students_visible_to_business(
    db: Session, business: BusinessProfile, candidates: list[StudentProfile]
) -> list[StudentProfile]:
    """Given a candidate pool (e.g. from the matching engine), strip out
    anyone this business isn't cleared to see. Called AFTER scoring so the
    matching engine doesn't need to know about safeguarding rules — a clean
    separation of concerns."""
    visible = []
    for student in candidates:
        decision = can_business_access_student(db, business, student)
        if decision.allowed:
            visible.append(student)
    return visible


def filter_projects_visible_to_student(student: StudentProfile, candidates: list[Project]) -> list[Project]:
    """A project posted by a business is only shown to a student if the
    business targeted that student's university AND band. (The underlying
    university-business agreement was already checked when the project was
    approved for posting — see requires_university_project_review.)"""
    visible = []
    for project in candidates:
        if student.university_id in project.target_university_ids and (
            not project.target_bands or student.band.value in project.target_bands
        ):
            visible.append(project)
    return visible
