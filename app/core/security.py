"""
Password hashing + JWT access/refresh token issuance.

Mobile note: native apps hold onto a long-lived refresh token in secure
device storage (Keychain / Keystore) and use it to silently mint new short
lived access tokens, so users aren't repeatedly asked to log back in.
"""
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from jose import jwt
from passlib.context import CryptContext

from app.core.config import settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def _create_token(subject: str, expires_delta: timedelta, token_type: str, extra_claims: Optional[dict] = None) -> str:
    now = datetime.now(timezone.utc)
    to_encode: dict[str, Any] = {
        "sub": subject,
        "type": token_type,
        "iat": now,
        "exp": now + expires_delta,
    }
    if extra_claims:
        to_encode.update(extra_claims)
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def create_access_token(user_id: str, role: str, university_id: Optional[str] = None) -> str:
    return _create_token(
        subject=user_id,
        expires_delta=timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES),
        token_type="access",
        extra_claims={"role": role, "university_id": university_id},
    )


def create_refresh_token(user_id: str) -> str:
    return _create_token(
        subject=user_id,
        expires_delta=timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
        token_type="refresh",
    )


def create_mfa_token(user_id: str) -> str:
    """Short-lived, single-purpose token issued by /auth/login when TOTP is
    enabled — proves the password check already passed, but is deliberately
    a different `type` than access/refresh tokens so it can't be used
    anywhere a real access token is expected, and expires in minutes, not
    the usual 30 (Technical Implementation Plan step 2.a.iv)."""
    return _create_token(subject=user_id, expires_delta=timedelta(minutes=5), token_type="mfa")


def decode_token(token: str) -> dict:
    """Raises jose.JWTError on invalid/expired tokens — caught by the caller."""
    return jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
