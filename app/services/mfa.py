"""
TOTP-based MFA (Technical Implementation Plan step 2.a.iv), required for
university_admin/platform_admin once enabled. Standard RFC 6238 TOTP via
pyotp — no external account or service needed; the only "external" thing
is the admin's own authenticator app (Google Authenticator, Authy,
1Password, etc.), which they already have.

Deliberately not enforced retroactively on every existing admin account —
there's no admin UI yet to walk someone through /mfa/setup, so hard-
blocking login for an account that was never given a chance to enable it
would just lock people out with no way back in. Enforcement is real and
immediate once `totp_enabled` is true (see auth.py's login endpoint); the
gap is only "not yet opted in", not "opted in but not enforced."
"""
import secrets

import pyotp
from passlib.context import CryptContext

from app.core.config import settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

BACKUP_CODE_COUNT = 8


def generate_totp_secret() -> str:
    return pyotp.random_base32()


def provisioning_uri(secret: str, email: str) -> str:
    """otpauth:// URI — any authenticator app can scan/import this directly
    (as a QR code rendered client-side, or pasted manually). No QR image is
    generated server-side: there's no admin UI yet to display one to, and
    the raw secret works equally well for manual entry in the meantime."""
    return pyotp.totp.TOTP(secret).provisioning_uri(name=email, issuer_name=settings.APP_NAME)


def verify_totp_code(secret: str, code: str) -> bool:
    # valid_window=1 tolerates one 30s step of clock drift either side —
    # without it, a slightly-off device clock makes MFA nearly unusable.
    return pyotp.TOTP(secret).verify(code, valid_window=1)


def generate_backup_codes() -> list[str]:
    """Returns BACKUP_CODE_COUNT plaintext codes — the only time they ever
    exist in plaintext. Caller stores only hash_backup_codes()'s output."""
    return [f"{secrets.token_hex(4)}-{secrets.token_hex(4)}" for _ in range(BACKUP_CODE_COUNT)]


def hash_backup_codes(codes: list[str]) -> list[str]:
    return [pwd_context.hash(code) for code in codes]


def consume_backup_code(hashed_codes: list[str], submitted_code: str) -> list[str] | None:
    """Returns the remaining hashed codes with the matching one removed
    (each code is single-use), or None if submitted_code doesn't match any
    of them. Callers must persist the returned list back onto the user."""
    for hashed in hashed_codes:
        if pwd_context.verify(submitted_code, hashed):
            remaining = hashed_codes[:]
            remaining.remove(hashed)
            return remaining
    return None
