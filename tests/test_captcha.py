"""
2.c.iii bot-protection tests. hCaptcha publishes a permanent, no-account
test key pair specifically for exercising the real siteverify API from
automated tests (https://docs.hcaptcha.com/#integration-testing-test-key-set)
— used here for a genuine live check, the same "hit the real third-party API,
don't just mock it" standard used for the HIBP breach check
(tests/test_password_policy.py).
"""
from app.core import config
from app.services import captcha

TEST_SECRET_KEY = "0x0000000000000000000000000000000000000000"
TEST_ALWAYS_PASSES_RESPONSE = "10000000-aaaa-bbbb-cccc-000000000001"


def test_disabled_when_no_secret_key_configured(monkeypatch):
    """Zero-friction default: no HCAPTCHA_SECRET_KEY set (the out-of-the-box
    dev/demo state) means every registration passes regardless of token,
    same as production code never having been wired up to a real Sentry/
    Stripe/Firebase account either."""
    monkeypatch.setattr(config.settings, "HCAPTCHA_SECRET_KEY", "")
    assert captcha.is_captcha_enabled() is False
    assert captcha.verify_captcha(None) is True
    assert captcha.verify_captcha("anything") is True


def test_missing_token_rejected_once_enabled(monkeypatch):
    monkeypatch.setattr(config.settings, "HCAPTCHA_SECRET_KEY", TEST_SECRET_KEY)
    assert captcha.verify_captcha(None) is False
    assert captcha.verify_captcha("") is False


def test_live_verification_against_real_hcaptcha_api(monkeypatch):
    """Genuine network call to hCaptcha's real siteverify endpoint, not
    mocked — confirms both the always-passes and always-fails test tokens
    actually round-trip correctly through verify_captcha()."""
    monkeypatch.setattr(config.settings, "HCAPTCHA_SECRET_KEY", TEST_SECRET_KEY)
    assert captcha.verify_captcha(TEST_ALWAYS_PASSES_RESPONSE) is True
    assert captcha.verify_captcha("a-token-hcaptcha-has-definitely-never-issued") is False


def test_fails_open_on_network_error(monkeypatch):
    def _raise(*args, **kwargs):
        import httpx

        raise httpx.ConnectTimeout("simulated outage")

    monkeypatch.setattr(config.settings, "HCAPTCHA_SECRET_KEY", TEST_SECRET_KEY)
    monkeypatch.setattr(captcha.httpx, "post", _raise)
    assert captcha.verify_captcha("some-token") is True


def test_captcha_site_key_endpoint_returns_configured_key(client):
    """2.c.iii's frontend widget (static/app/js/main.js) fetches this
    rather than hardcoding a site key, so a real key can replace the
    default hCaptcha test key with no frontend code change."""
    response = client.get("/api/v1/auth/captcha-site-key")
    assert response.status_code == 200
    assert response.json() == {"site_key": config.settings.HCAPTCHA_SITE_KEY}
