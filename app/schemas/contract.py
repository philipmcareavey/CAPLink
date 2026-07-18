from datetime import date
from typing import List, Optional

from pydantic import BaseModel, ConfigDict

from app.models.enums import ContractStatus, MilestoneStatus


class MilestoneCreate(BaseModel):
    description: str
    due_date: Optional[date] = None
    payment_amount_gbp: float


class MilestoneOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    description: str
    due_date: Optional[date]
    payment_amount_gbp: float
    status: MilestoneStatus


class ContractCreate(BaseModel):
    application_id: str
    milestones: List[MilestoneCreate]


class ContractOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    project_id: str
    student_id: str
    business_id: str
    status: ContractStatus
    ip_assignment_accepted: bool
    nda_accepted: bool
    milestones: List[MilestoneOut]


class ContractWithCounterpart(ContractOut):
    """ContractOut plus enough of the other party's identity to drive a
    'message them' action from a contract card without a second round trip."""
    project_title: str
    counterpart_user_id: str
    counterpart_name: str
