from sqlalchemy import Boolean, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base_class import Base, TimestampMixin, UUIDPrimaryKeyMixin


class MessageThread(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "message_threads"

    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), nullable=True)
    student_user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False)
    business_user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False)


class Message(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "messages"

    thread_id: Mapped[str] = mapped_column(ForeignKey("message_threads.id"), nullable=False)
    sender_user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)

    # Before a contract exists, messages are scanned for off-platform contact
    # attempts (phone numbers, external emails, "pay me directly" language)
    # to protect students and preserve platform fee integrity.
    is_flagged: Mapped[bool] = mapped_column(Boolean, default=False)
    flagged_reason: Mapped[str] = mapped_column(String(255), nullable=True)
    is_read: Mapped[bool] = mapped_column(Boolean, default=False)
