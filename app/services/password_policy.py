"""
Password strength + breach-list checking (Technical Implementation Plan
step 2.a.i), run at registration and password change.

Two independent, composable checks:
- Local complexity rules — instant, no network.
- The "Pwned Passwords" k-anonymity API (haveibeenpwned.com/API/v3#PwnedPasswords)
  — free, keyless, no account needed. Only the first 5 hex characters of the
  password's SHA-1 hash are ever sent, so the real password (or even a full
  hash of it) never leaves this process.
"""
import hashlib
import logging

import httpx

from app.core.config import settings

logger = logging.getLogger("caplink.password_policy")

MIN_LENGTH = 8


class PasswordPolicyError(ValueError):
    """Raised with a user-facing reason when a password fails policy."""


def validate_password_complexity(password: str) -> None:
    if len(password) < MIN_LENGTH:
        raise PasswordPolicyError(f"Password must be at least {MIN_LENGTH} characters long.")
    if not any(c.isupper() for c in password):
        raise PasswordPolicyError("Password must contain at least one uppercase letter.")
    if not any(c.islower() for c in password):
        raise PasswordPolicyError("Password must contain at least one lowercase letter.")
    if not any(c.isdigit() for c in password):
        raise PasswordPolicyError("Password must contain at least one digit.")


def check_password_breached(password: str) -> bool:
    """
    True if the password appears in a known breach corpus. Fails OPEN
    (returns False, i.e. "not known to be breached") on any network/API
    error — a breach check is a genuine security nice-to-have, but it
    shouldn't turn a third-party outage into an outage of registration/
    password-change for this whole platform.
    """
    # SHA-1 here is HIBP's own protocol requirement, not used for secrecy.
    sha1 = hashlib.sha1(password.encode("utf-8")).hexdigest().upper()
    prefix, suffix = sha1[:5], sha1[5:]
    try:
        response = httpx.get(f"https://api.pwnedpasswords.com/range/{prefix}", timeout=3.0)
        response.raise_for_status()
    except httpx.HTTPError:
        logger.warning("password_breach_check_unavailable")
        return False
    for line in response.text.splitlines():
        candidate_suffix, _, _count = line.partition(":")
        if candidate_suffix == suffix:
            return True
    return False


def validate_password(password: str, *, check_breach: bool = True) -> None:
    """Raises PasswordPolicyError with a user-facing reason on the first
    check that fails — complexity first, since it's free, before spending
    a network round-trip on the breach check."""
    validate_password_complexity(password)
    if check_breach and settings.PASSWORD_BREACH_CHECK_ENABLED and check_password_breached(password):
        raise PasswordPolicyError(
            "This password has appeared in a known data breach — please choose a different one."
        )
