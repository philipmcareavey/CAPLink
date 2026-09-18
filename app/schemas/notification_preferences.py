from pydantic import BaseModel


class NotificationPreferenceItem(BaseModel):
    template_key: str
    label: str
    enabled: bool


class NotificationPreferencesOut(BaseModel):
    preferences: list[NotificationPreferenceItem]


class NotificationPreferencesUpdate(BaseModel):
    opted_out: list[str]
