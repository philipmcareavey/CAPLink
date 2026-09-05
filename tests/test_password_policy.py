import pytest

from app.services.password_policy import (
    PasswordPolicyError,
    check_password_breached,
    validate_password,
    validate_password_complexity,
)


def test_rejects_too_short():
    with pytest.raises(PasswordPolicyError, match="at least 8 characters"):
        validate_password_complexity("Ab1")


def test_rejects_no_uppercase():
    with pytest.raises(PasswordPolicyError, match="uppercase"):
        validate_password_complexity("lowercase1")


def test_rejects_no_lowercase():
    with pytest.raises(PasswordPolicyError, match="lowercase"):
        validate_password_complexity("UPPERCASE1")


def test_rejects_no_digit():
    with pytest.raises(PasswordPolicyError, match="digit"):
        validate_password_complexity("NoDigitsHere")


def test_accepts_a_genuinely_strong_password():
    validate_password_complexity("Xk9mQ2vLp7z")  # should not raise


def test_breach_check_fails_open_on_network_error(monkeypatch):
    """A third-party outage must never block registration/login — see the
    docstring on check_password_breached."""
    def _boom(*args, **kwargs):
        raise __import__("httpx").ConnectError("simulated network failure")

    monkeypatch.setattr("app.services.password_policy.httpx.get", _boom)
    assert check_password_breached("whatever-password") is False


def test_breach_check_detects_a_match(monkeypatch):
    # SHA-1("password") = 5BAA61E4C9B93F3F0682250B6CF8331B7EE68FD8 -> prefix
    # 5BAA6, suffix 1E4C9B93F3F0682250B6CF8331B7EE68FD8.
    class _FakeResponse:
        text = "1E4C9B93F3F0682250B6CF8331B7EE68FD8:3730471\nOTHERSUFFIX:1"

        def raise_for_status(self):
            pass

    monkeypatch.setattr("app.services.password_policy.httpx.get", lambda *a, **k: _FakeResponse())
    assert check_password_breached("password") is True


def test_breach_check_no_match(monkeypatch):
    class _FakeResponse:
        text = "SOMEOTHERSUFFIXENTIRELY:1"

        def raise_for_status(self):
            pass

    monkeypatch.setattr("app.services.password_policy.httpx.get", lambda *a, **k: _FakeResponse())
    assert check_password_breached("a-genuinely-unique-password") is False


def test_validate_password_raises_on_breach(monkeypatch):
    monkeypatch.setattr("app.services.password_policy.check_password_breached", lambda pw: True)
    with pytest.raises(PasswordPolicyError, match="known data breach"):
        validate_password("Xk9mQ2vLp7z")


def test_validate_password_skips_breach_check_when_disabled(monkeypatch):
    monkeypatch.setattr("app.services.password_policy.check_password_breached", lambda pw: True)
    validate_password("Xk9mQ2vLp7z", check_breach=False)  # should not raise despite the monkeypatch above
