from typing import List, Optional

from pydantic import BaseModel, Field


class TokenPair(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RefreshRequest(BaseModel):
    refresh_token: str


class TokenPayload(BaseModel):
    sub: str
    type: str
    role: Optional[str] = None
    university_id: Optional[str] = None


# ---------- MFA (2.a.iv) ----------

class MfaRequired(BaseModel):
    """Returned from /auth/login instead of TokenPair when the account has
    TOTP enabled — exchange mfa_token + a code at /auth/mfa/verify for the
    real TokenPair."""
    mfa_required: bool = True
    mfa_token: str


class MfaVerifyRequest(BaseModel):
    mfa_token: str
    code: str


class MfaSetupResponse(BaseModel):
    secret: str
    provisioning_uri: str


class MfaEnableRequest(BaseModel):
    code: str


class MfaEnableResponse(BaseModel):
    backup_codes: List[str] = Field(description="Shown once, never retrievable again — store them safely.")


class MfaDisableRequest(BaseModel):
    code: str
