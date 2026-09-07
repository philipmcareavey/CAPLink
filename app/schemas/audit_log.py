from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict


class AuditLogOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    actor_user_id: str
    action: str
    target_type: str
    target_id: Optional[str]
    details: Optional[dict]
    created_at: datetime
