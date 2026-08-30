from typing import Optional, TYPE_CHECKING

from sqlalchemy import Boolean, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.models.enums import DevicePlatform

if TYPE_CHECKING:
    from app.models.user import User


class Device(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """A registered mobile/web client for push notifications."""
    __tablename__ = "devices"

    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False)
    platform: Mapped[DevicePlatform] = mapped_column(nullable=False)
    push_token: Mapped[str] = mapped_column(String(500), nullable=False)  # FCM/APNs token
    app_version: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    user: Mapped["User"] = relationship(back_populates="devices")
