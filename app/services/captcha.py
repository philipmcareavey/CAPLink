"""
Bot protection on public registration endpoints (Technical Implementation
Plan step 2.c.iii), via hCaptcha's siteverify API — same "real code, external
account is the manual step" shape as Sentry (1.c.ii) and the HIBP breach
check (2.a.i): nothing here needs an account to exist for the code itself to
be correct, but there's genuinely nothing to verify end-to-end without one.

hCaptcha publishes permanent, no-account-needed test credentials
(https://docs.hcaptcha.com/#integration-testing-test-key-set) specifically
for exercising the real API from automated tests — see tests/test_captcha.py,
which hits the live endpoint with them rather than mocking the call.
"""
import logging

import httpx

from app.core.config import settings

logger = logging.getLogger("caplink.captcha")

HCAPTCHA_VERIFY_URL = "https://hcaptcha.com/siteverify"


def is_captcha_enabled() -> bool:
    """No secret key configured means bot protection isn't set up yet — same
    zero-friction-until-configured shape as Sentry's empty SENTRY_DSN, so
    local dev/demo registration keeps working with no extra setup."""
    return settings.CAPTCHA_ENABLED and bool(settings.HCAPTCHA_SECRET_KEY)


def verify_captcha(token: str | None) -> bool:
    """True if the token is a genuine, unexpired hCaptcha solve. Fails OPEN
    (returns True) on a network/API error, matching check_password_breached's
    reasoning in app/services/password_policy.py: an hCaptcha outage
    shouldn't turn into an outage of registration for the whole platform,
    especially with per-IP/per-account rate limiting and account lockout
    (2.a.ii) already covering the same abuse this is meant to slow down."""
    if not is_captcha_enabled():
        return True
    if not token:
        return False

    try:
        response = httpx.post(
            HCAPTCHA_VERIFY_URL,
            data={"secret": settings.HCAPTCHA_SECRET_KEY, "response": token},
            timeout=5.0,
        )
        response.raise_for_status()
    except httpx.HTTPError:
        logger.warning("captcha_check_unavailable")
        return True

    return bool(response.json().get("success"))
