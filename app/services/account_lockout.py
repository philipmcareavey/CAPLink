"""
Per-account progressive lockout (Technical Implementation Plan step
2.a.ii). The per-IP half of that step is separate — see the slowapi
Limiter wired up in app/main.py and applied to the login/register routes;
this module only ever looks at one User row at a time.
"""
from datetime import datetime, timedelta

from app.core.config import settings
from app.models.user import User

# Naive UTC throughout, matching app/db/base_class.py's TimestampMixin —
# mixing naive and timezone-aware datetimes on the same column raises
# TypeError the moment one gets compared against the other.


def is_locked(user: User) -> bool:
    return user.locked_until is not None and user.locked_until > datetime.utcnow()


def register_failed_attempt(user: User) -> None:
    """Call after a wrong password. Locks out once ACCOUNT_LOCKOUT_THRESHOLD
    is reached, then doubles the lockout duration on every attempt past
    that (5, 10, 20, 40... minutes) rather than a single fixed window —
    makes an automated retry loop increasingly expensive to keep running,
    not just briefly inconvenienced once."""
    user.failed_login_attempts += 1
    if user.failed_login_attempts >= settings.ACCOUNT_LOCKOUT_THRESHOLD:
        backoff_steps = user.failed_login_attempts - settings.ACCOUNT_LOCKOUT_THRESHOLD
        minutes = settings.ACCOUNT_LOCKOUT_BASE_MINUTES * (2**backoff_steps)
        user.locked_until = datetime.utcnow() + timedelta(minutes=minutes)


def register_successful_login(user: User) -> None:
    user.failed_login_attempts = 0
    user.locked_until = None
