"""
Development-only payment simulation. Every other real integration in this
codebase stays zero-friction in local dev without any account (CAPTCHA is
a no-op with no key, email verification auto-verifies, HIBP fails open) —
Stripe genuinely can't follow that pattern for staging/production (see
StripeNotConfigured's docstring: payments must fail closed there, a broken
setup silently "succeeding" would corrupt real financial state). But
failing closed in `development` too would break the existing zero-setup
`/app` and `/demo` reference UIs, which have never needed any external
account for anything before this epic — that's a real regression, not
just an inconvenience, and it directly contradicts this project's
repeatedly-stated local-dev priority (see CLAUDE.md).

The resolution: simulate Stripe entirely in `development` when no real key
is configured — every stripe_*.py module checks `is_simulated()` first and
returns a synthetic-but-consistent fake object instead of ever calling the
real SDK. `staging`/`production` never simulate, regardless of whether a
key happens to be missing there — see each module's `_require_stripe_configured`
for where that boundary is actually enforced.
"""
import uuid

from app.core.config import settings


def is_simulated() -> bool:
    return settings.ENVIRONMENT == "development" and not settings.STRIPE_SECRET_KEY


def fake_id(prefix: str) -> str:
    return f"{prefix}_dev_{uuid.uuid4().hex[:16]}"
