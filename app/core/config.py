"""
CAPLink — central configuration.

Reads from environment variables / .env. See .env.example (development),
.env.staging.example, and .env.production.example for the full list per
environment. CAPLink is a licensed, multi-tenant platform: each university is
a *tenant* with its own branding, subdomain, and safeguarding policies, but
all tenants share this single backend deployment.
"""
import os
from typing import List, Literal

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# pydantic-settings picks its env_file once, at class-definition time, so
# *which* file to load has to be decided from the raw process environment
# before Settings exists — the values inside it are still fully validated by
# the Settings model below once loaded. Development keeps loading plain
# `.env` (unchanged, zero-friction local default); staging/production look
# for their own named file and simply fall back to whatever the process
# environment already provides (e.g. Render's injected env vars) if no such
# file is present on disk.
_ENVIRONMENT = os.getenv("ENVIRONMENT", "development")
_ENV_FILE = ".env" if _ENVIRONMENT == "development" else f".env.{_ENVIRONMENT}"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=_ENV_FILE, case_sensitive=False, extra="ignore")

    APP_NAME: str = "CAPLink"
    ENVIRONMENT: Literal["development", "staging", "production"] = "development"

    # Security
    SECRET_KEY: str = "dev-only-secret-change-me"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 30

    # Database
    DATABASE_URL: str = "sqlite:///./caplink.db"

    # CORS — mobile apps call in via capacitor://, ionic://, or native http clients
    CORS_ORIGINS: str = "http://localhost:3000"

    # Payments
    STRIPE_SECRET_KEY: str = ""
    STRIPE_WEBHOOK_SECRET: str = ""
    PLATFORM_FEE_PERCENT: float = 12.5

    # Push notifications
    FIREBASE_CREDENTIALS_JSON: str = ""

    # Observability
    LOG_LEVEL: str = "INFO"
    # Empty = error tracking disabled (see app/core/observability.py) — a
    # real Sentry account/project is a manual step (Technical Implementation
    # Plan step 1.c.ii), same pattern as Stripe/Firebase above.
    SENTRY_DSN: str = ""

    # Licensing
    DEFAULT_UNIVERSITY_TRIAL_DAYS: int = 30

    # Pagination defaults (mobile clients should always page)
    DEFAULT_PAGE_SIZE: int = 20
    MAX_PAGE_SIZE: int = 50

    @property
    def cors_origin_list(self) -> List[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]

    @model_validator(mode="after")
    def _reject_dev_secrets_outside_dev(self) -> "Settings":
        """Staging/production must never silently run on dev's placeholder
        secrets or SQLite — this guardrail, not just file separation, is the
        actual point of having per-environment config at all.

        Both checks cover staging and production equally as of 2026-08-30:
        Render's staging deploy (`caplink-staging-db`, see render.yaml) was
        confirmed actually running on Postgres — its deploy logs showed
        `Context impl PostgresqlImpl` and the baseline migration applying
        fresh — so there's no longer a sequencing reason to exempt staging.
        """
        if self.ENVIRONMENT == "development":
            return self
        if self.SECRET_KEY == "dev-only-secret-change-me":
            raise ValueError(
                f"SECRET_KEY is still the development default in {self.ENVIRONMENT} — "
                f"set a real value (see .env.{self.ENVIRONMENT}.example)."
            )
        if self.DATABASE_URL.startswith("sqlite"):
            raise ValueError(
                f"DATABASE_URL is SQLite in {self.ENVIRONMENT} — point it at a real "
                f"Postgres instance (see .env.{self.ENVIRONMENT}.example)."
            )
        return self


settings = Settings()
