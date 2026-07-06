from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_business
from app.db.session import get_db
from app.models.application import Application
from app.models.contract import Contract, Milestone
from app.models.enums import ApplicationStatus, ContractStatus, MilestoneStatus
from app.models.project import Project
from app.models.user import BusinessProfile, User
from app.schemas.contract import ContractCreate, ContractOut, MilestoneOut
from app.services.notifications import notify_from_template

router = APIRouter(prefix="/contracts", tags=["contracts"])


@router.post("", response_model=ContractOut, status_code=status.HTTP_201_CREATED)
def create_contract(
    payload: ContractCreate, db: Session = Depends(get_db), business_user: User = Depends(require_business)
):
    application = db.query(Application).filter(Application.id == payload.application_id).first()
    if application is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Application not found")

    project = db.query(Project).filter(Project.id == application.project_id).first()
    business = db.query(BusinessProfile).filter(BusinessProfile.user_id == business_user.id).first()
    if project.business_id != business.id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Not your project")

    application.status = ApplicationStatus.ACCEPTED
    project.status = project.status.__class__.IN_PROGRESS

    contract = Contract(
        project_id=project.id,
        application_id=application.id,
        student_id=application.student_id,
        business_id=business.id,
    )
    db.add(contract)
    db.flush()

    for m in payload.milestones:
        db.add(
            Milestone(
                contract_id=contract.id,
                description=m.description,
                due_date=m.due_date,
                payment_amount_gbp=m.payment_amount_gbp,
            )
        )
    db.commit()
    db.refresh(contract)
    return contract


@router.post("/{contract_id}/accept-terms", response_model=ContractOut)
def accept_terms(
    contract_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)
):
    """Both student and business must accept the IP-assignment / NDA clauses
    before the contract is considered fully active."""
    contract = db.query(Contract).filter(Contract.id == contract_id).first()
    if contract is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Contract not found")
    contract.ip_assignment_accepted = True
    contract.nda_accepted = True
    db.commit()
    db.refresh(contract)
    return contract


@router.post("/milestones/{milestone_id}/submit", response_model=MilestoneOut)
def submit_milestone(milestone_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """Student marks a milestone's deliverable as submitted."""
    milestone = db.query(Milestone).filter(Milestone.id == milestone_id).first()
    if milestone is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Milestone not found")
    milestone.status = MilestoneStatus.SUBMITTED
    db.commit()
    db.refresh(milestone)
    return milestone


@router.post("/milestones/{milestone_id}/approve-and-pay", response_model=MilestoneOut)
def approve_and_pay_milestone(
    milestone_id: str, db: Session = Depends(get_db), business_user: User = Depends(require_business)
):
    """
    Business approves the deliverable and releases escrowed payment.
    Stripe integration point: create/capture a PaymentIntent here in
    production (see app/services — a payments.py module would wrap the
    Stripe SDK using settings.STRIPE_SECRET_KEY).
    """
    milestone = db.query(Milestone).filter(Milestone.id == milestone_id).first()
    if milestone is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Milestone not found")

    milestone.status = MilestoneStatus.PAID
    milestone.stripe_payment_intent_id = "pi_placeholder_replace_with_real_stripe_call"
    db.commit()
    db.refresh(milestone)

    contract = db.query(Contract).filter(Contract.id == milestone.contract_id).first()
    from app.models.user import StudentProfile  # local import avoids circular import at module load

    student_user_id = (
        db.query(StudentProfile.user_id).filter(StudentProfile.id == contract.student_id).scalar()
    )
    notify_from_template(
        db, student_user_id, "milestone_paid", amount=milestone.payment_amount_gbp, milestone=milestone.description
    )
    return milestone
