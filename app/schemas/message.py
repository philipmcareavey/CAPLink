from datetime import datetime

from pydantic import BaseModel, ConfigDict


class ThreadCreate(BaseModel):
    project_id: str | None = None
    other_user_id: str  # the business or student on the other side


class MessageCreate(BaseModel):
    thread_id: str
    content: str


class MessageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    thread_id: str
    sender_user_id: str
    content: str
    is_flagged: bool
    is_read: bool
    created_at: datetime
