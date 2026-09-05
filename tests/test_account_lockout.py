from datetime import datetime, timedelta

from app.core.config import settings
from app.models.enums import UserRole
from app.models.user import User
from app.services.account_lockout import is_locked, register_failed_attempt, register_successful_login


def _make_user(**overrides):
    # failed_login_attempts=0 explicitly: the model's `default=0` is a
    # SQLAlchemy column default applied at flush/INSERT time, not at bare
    # Python object construction — a real DB row always has 0, but a User()
    # built directly (no session, as here) would otherwise have None.
    defaults = dict(
        email="test@example.com", hashed_password="x", role=UserRole.STUDENT, full_name="Test",
        failed_login_attempts=0,
    )
    defaults.update(overrides)
    return User(**defaults)


def test_not_locked_by_default():
    user = _make_user()
    assert is_locked(user) is False


def test_failed_attempts_below_threshold_do_not_lock():
    user = _make_user()
    for _ in range(settings.ACCOUNT_LOCKOUT_THRESHOLD - 1):
        register_failed_attempt(user)
    assert is_locked(user) is False
    assert user.locked_until is None


def test_reaching_threshold_locks_the_account():
    user = _make_user()
    for _ in range(settings.ACCOUNT_LOCKOUT_THRESHOLD):
        register_failed_attempt(user)
    assert is_locked(user) is True
    assert user.locked_until is not None
    assert user.locked_until > datetime.utcnow()


def test_backoff_grows_with_repeated_attempts_past_the_threshold():
    user = _make_user()
    for _ in range(settings.ACCOUNT_LOCKOUT_THRESHOLD):
        register_failed_attempt(user)
    first_lockout = user.locked_until

    register_failed_attempt(user)  # one more attempt past the threshold
    second_lockout = user.locked_until

    assert second_lockout > first_lockout  # progressively longer, not a fixed window


def test_successful_login_resets_everything():
    user = _make_user(failed_login_attempts=3, locked_until=datetime.utcnow() + timedelta(minutes=5))
    register_successful_login(user)
    assert user.failed_login_attempts == 0
    assert user.locked_until is None
    assert is_locked(user) is False


def test_an_expired_lockout_no_longer_counts_as_locked():
    user = _make_user(locked_until=datetime.utcnow() - timedelta(minutes=1))
    assert is_locked(user) is False
