from pydantic import BaseModel, Field

from app.models.enums import DevicePlatform


class DeviceRegister(BaseModel):
    platform: DevicePlatform
    push_token: str = Field(min_length=1, max_length=2_000)
    app_version: str | None = Field(default=None, max_length=50)
