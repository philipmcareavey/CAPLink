from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_business
from app.db.session import get_db
from app.models.application import Application
from app.models.contract import Contract, Milestone
from app.models.enums import ApplicationStatus, MilestoneStatus, UserRole
from app.models.project import Project
from app.models.user import BusinessProfile, StudentProfile, User
from app.schemas.contract import ContractCreate, ContractOut, ContractWithCounterpart, MilestoneOut
from app.services import payroll, stripe_payments
from app.services.notifications import notify_from_template
from app.services.stripe_payments import MilestonePaymentError

router = APIRouter(prefix="/contracts", tags=["contracts"])


def _assert_is_contract_business(db: Session, contract: Contract, business_user: User) -> BusinessProfile:
    """A contract's only two legitimate actors are its own student and its
    own business — this and _assert_is_contract_party below are new checks
    added while wiring up real payments (Technical Implementation Plan
    3.a/3.b). Before this, any authenticated business could approve-and-pay
    (or accept terms on, or — for a student — submit a milestone on) ANY
    contract, not just their own: harmless while payment was a placeholder
    string, a real vulnerability once approve-and-pay actually captures
    money and refund actually moves it back."""
    business = db.query(BusinessProfile).filter(BusinessProfile.user_id == business_user.id).first()
    assert business is not None, "require_business guarantees a BusinessProfile row exists"
    if contract.business_id != business.id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Not your contract")
    return business


def _assert_is_contract_party(db: Session, contract: Contract, user: User) -> None:
    if user.role == UserRole.BUSINESS:
        business = db.query(BusinessProfile).filter(BusinessProfile.user_id == user.id).first()
        if business is None or contract.business_id != business.id:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Not your contract")
    elif user.role == UserRole.STUDENT:
        student = db.query(StudentProfile).filter(StudentProfile.user_id == user.id).first()
        if student is None or contract.student_id != student.id:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Not your contract")
    else:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Not permitted for this role")


@router.post("", response_model=ContractOut, status_code=status.HTTP_201_CREATED)
def create_contract(
    payload: ContractCreate, db: Session = Depends(get_db), business_user: User = Depends(require_business)
):
    """Hires an applicant via a milestone-based contract. Every milestone's
    full amount is authorised (escrow-held) on the business's card right
    now, not captured until approval — see README's "Payments & payroll"
    section. Fails with 402 if either side hasn't finished payment setup."""
    application = db.query(Application).filter(Application.id == payload.application_id).first()
    if application is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Application not found")

    project = db.query(Project).filter(Project.id == application.project_id).first()
    assert project is not None, "Application.project_id is a NOT NULL FK to projects"
    business = db.query(BusinessProfile).filter(BusinessProfile.user_id == business_user.id).first()
    assert business is not None, "require_business guarantees a BusinessProfile row exists"
    if project.business_id != business.id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Not your project")

    student = db.query(StudentProfile).filter(StudentProfile.id == application.student_id).first()
    assert student is not None, "Application.student_id is a NOT NULL FK to student_profiles"

    payment_rail = payroll.determine_payment_rail(student)

    application.status = ApplicationStatus.ACCEPTED
    project.status = project.status.__class__.IN_PROGRESS

    contract = Contract(
        project_id=project.id,
        application_id=application.id,
        student_id=application.student_id,
        business_id=business.id,
        payment_rail=payment_rail,
    )
    db.add(contract)
    db.flush()

    milestones = []
    for m in payload.milestones:
        milestone = Milestone(
            contract_id=contract.id,
            description=m.description,
            due_date=m.due_date,
            payment_amount_gbp=m.payment_amount_gbp,
        )
        db.add(milestone)
        milestones.append(milestone)
    db.flush()

    # Technical Implementation Plan 3.b.i — every milestone's full amount is
    # authorized (held on the business's card) right now, at creation time,
    # not captured until approval. If ANY milestone fails to authorize, the
    # whole contract is rolled back rather than left half-funded — a
    # partially-payable contract is worse than no contract at all.
    for milestone in milestones:
        try:
            stripe_payments.authorize_milestone_payment(milestone, business, student, payment_rail)
        except MilestonePaymentError as exc:
            db.rollback()
            raise HTTPException(status.HTTP_402_PAYMENT_REQUIRED, str(exc))

    db.commit()
    db.refresh(contract)
    return contract


@router.get("/mine", response_model=list[ContractWithCounterpart])
def get_my_contracts(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """Role-aware: a student sees contracts where they're the student side,
    a business sees contracts where they're the business side. Reuses
    ContractOut as-is — milestones come for free via the model's relationship."""
    if user.role == UserRole.STUDENT:
        student = db.query(StudentProfile).filter(StudentProfile.user_id == user.id).first()
        assert student is not None, "a STUDENT-role user always has a StudentProfile (see auth.py registration)"
        query = db.query(Contract).filter(Contract.student_id == student.id)
    elif user.role == UserRole.BUSINESS:
        business = db.query(BusinessProfile).filter(BusinessProfile.user_id == user.id).first()
        assert business is not None, "a BUSINESS-role user always has a BusinessProfile (see auth.py registration)"
        query = db.query(Contract).filter(Contract.business_id == business.id)
    else:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Not permitted for this role")

    contracts = query.order_by(Contract.created_at.desc()).all()

    results = []
    for contract in contracts:
        student = db.query(StudentProfile).filter(StudentProfile.id == contract.student_id).first()
        assert student is not None, "Contract.student_id is a NOT NULL FK to student_profiles"
        business = db.query(BusinessProfile).filter(BusinessProfile.id == contract.business_id).first()
        assert business is not None, "Contract.business_id is a NOT NULL FK to business_profiles"
        project = db.query(Project).filter(Project.id == contract.project_id).first()
        if user.role == UserRole.STUDENT:
            counterpart_user_id, counterpart_name = business.user_id, business.company_name
        else:
            counterpart_user_id, counterpart_name = student.user_id, student.user.full_name
        results.append(
            ContractWithCounterpart(
                **ContractOut.model_validate(contract).model_dump(),
                project_title=project.title if project else "",
                counterpart_user_id=counterpart_user_id,
                counterpart_name=counterpart_name,
            )
        )
    return results


@router.post("/{contract_id}/accept-terms", response_model=ContractOut)
def accept_terms(
    contract_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)
):
    """Both student and business must accept the IP-assignment / NDA clauses
    before the contract is considered fully active."""
    contract = db.query(Contract).filter(Contract.id == contract_id).first()
    if contract is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Contract not found")
    _assert_is_contract_party(db, contract, user)
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
    contract = db.query(Contract).filter(Contract.id == milestone.contract_id).first()
    assert contract is not None, "Milestone.contract_id is a NOT NULL FK to contracts"
    _assert_is_contract_party(db, contract, user)
    if user.role != UserRole.STUDENT:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Only the student on this contract can submit a milestone")
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
    Technical Implementation Plan 3.b.ii — capture is the real payment
    action (see app/services/stripe_payments.py's docstring: this single
    call both collects CAPLink's platform fee and transfers the remainder
    to the student's Connect account, on the self-employed rail).
    """
    milestone = db.query(Milestone).filter(Milestone.id == milestone_id).first()
    if milestone is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Milestone not found")

    contract = db.query(Contract).filter(Contract.id == milestone.contract_id).first()
    assert contract is not None, "Milestone.contract_id is a NOT NULL FK to contracts"
    _assert_is_contract_business(db, contract, business_user)

    try:
        stripe_payments.capture_milestone_payment(milestone)
    except MilestonePaymentError as exc:
        db.rollback()
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, str(exc))

    milestone.status = MilestoneStatus.PAID
    db.commit()
    db.refresh(milestone)

    student_user_id = (
        db.query(StudentProfile.user_id).filter(StudentProfile.id == contract.student_id).scalar()
    )
    notify_from_template(
        db, student_user_id, "milestone_paid", amount=milestone.payment_amount_gbp, milestone=milestone.description
    )
    return milestone


@router.post("/milestones/{milestone_id}/refund", response_model=MilestoneOut)
def refund_milestone(
    milestone_id: str, db: Session = Depends(get_db), business_user: User = Depends(require_business)
):
    """Technical Implementation Plan 3.b.iii. Only the business on this
    contract can initiate a refund of a milestone they've already paid —
    a deliberately narrow surface; a wider dispute-resolution workflow
    (platform-mediated, student-initiated) is future work, not this step."""
    milestone = db.query(Milestone).filter(Milestone.id == milestone_id).first()
    if milestone is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Milestone not found")

    contract = db.query(Contract).filter(Contract.id == milestone.contract_id).first()
    assert contract is not None, "Milestone.contract_id is a NOT NULL FK to contracts"
    _assert_is_contract_business(db, contract, business_user)

    if milestone.status != MilestoneStatus.PAID:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Only a paid milestone can be refunded")

    try:
        stripe_payments.refund_milestone_payment(milestone, reason="business_initiated_refund")
    except MilestonePaymentError as exc:
        db.rollback()
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, str(exc))

    milestone.status = MilestoneStatus.REFUNDED
    db.commit()
    db.refresh(milestone)
    return milestone


@router.post("/milestones/{milestone_id}/reject", response_model=MilestoneOut)
def reject_milestone(
    milestone_id: str, db: Session = Depends(get_db), business_user: User = Depends(require_business)
):
    """Technical Implementation Plan 3.b.iii's other half: a business
    rejects a submitted deliverable BEFORE ever capturing payment. Distinct
    from /refund above (which reverses money already captured) — this
    releases the card authorization outright via
    stripe_payments.cancel_milestone_authorization, since nothing was ever
    actually taken from the business's card."""
    milestone = db.query(Milestone).filter(Milestone.id == milestone_id).first()
    if milestone is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Milestone not found")

    contract = db.query(Contract).filter(Contract.id == milestone.contract_id).first()
    assert contract is not None, "Milestone.contract_id is a NOT NULL FK to contracts"
    _assert_is_contract_business(db, contract, business_user)

    if milestone.status != MilestoneStatus.SUBMITTED:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Only a submitted, unpaid milestone can be rejected")

    try:
        stripe_payments.cancel_milestone_authorization(milestone)
    except MilestonePaymentError as exc:
        db.rollback()
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, str(exc))

    milestone.status = MilestoneStatus.REJECTED
    db.commit()
    db.refresh(milestone)
    return milestone
