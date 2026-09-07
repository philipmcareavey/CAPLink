from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

# Technical Implementation Plan 2.c.ii — a message body is the highest-volume
# free-text input in the whole API, so it gets an explicit cap rather than
# relying on the Text column to be unbounded.
CONTENT_MAX_LENGTH = 5_000


class ThreadCreate(BaseModel):
    project_id: str | None = Field(default=None, max_length=36)
    other_user_id: str = Field(max_length=36)  # the business or student on the other side


class MessageCreate(BaseModel):
    thread_id: str = Field(max_length=36)
    content: str = Field(min_length=1, max_length=CONTENT_MAX_LENGTH)


class MessageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    thread_id: str
    sender_user_id: str
    content: str
    is_flagged: bool
    is_read: bool
    created_at: datetime


class ThreadSummaryOut(BaseModel):
    thread_id: str
    project_id: str | None
    counterpart_user_id: str
    counterpart_name: str
    last_message_preview: str | None
    last_message_at: datetime | None
    unread_count: int
