from pydantic import BaseModel

from app.models.enums import DevicePlatform


class DeviceRegister(BaseModel):
    platform: DevicePlatform
    push_token: str
    app_version: str | None = None
