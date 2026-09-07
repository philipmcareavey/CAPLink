from datetime import date, datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import ContractStatus, MilestoneStatus, PaymentRail


class MilestoneCreate(BaseModel):
    description: str = Field(min_length=1, max_length=2_000)
    due_date: Optional[date] = None
    payment_amount_gbp: float = Field(ge=0, le=1_000_000)


class MilestoneOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    description: str
    due_date: Optional[date]
    payment_amount_gbp: float
    status: MilestoneStatus
    # Stripe's own PaymentIntent status string, not our workflow status
    # above — see app/models/contract.py's comment on why these are kept
    # separate. Never exposes stripe_payment_intent_id itself; that's an
    # internal reference, not something a client needs.
    stripe_payment_intent_status: Optional[str] = None
    captured_at: Optional[datetime] = None


class ContractCreate(BaseModel):
    application_id: str = Field(max_length=36)
    milestones: List[MilestoneCreate] = Field(min_length=1, max_length=50)


class ContractOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    project_id: str
    student_id: str
    business_id: str
    status: ContractStatus
    ip_assignment_accepted: bool
    nda_accepted: bool
    payment_rail: PaymentRail
    milestones: List[MilestoneOut]


class ContractWithCounterpart(ContractOut):
    """ContractOut plus enough of the other party's identity to drive a
    'message them' action from a contract card without a second round trip."""
    project_title: str
    counterpart_user_id: str
    counterpart_name: str
