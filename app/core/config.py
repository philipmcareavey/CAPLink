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
        secrets — this guardrail, not just file separation, is the actual
        point of having per-environment config at all.

        The SQLite check is production-only, not staging-too, on purpose —
        not because staging is exempt in principle, but for sequencing:
        render.yaml now *declares* a staging Postgres instance (Technical
        Implementation Plan step 1.a.iv), but declaring it isn't the same as
        it existing — that only happens once the blueprint is actually
        synced on Render. Tightening this check in the same change that
        declares the database would mean the staging deploy starts failing
        the instant this ships, before the database is real. Once the
        blueprint's been synced and the staging service is confirmed
        running on Postgres (check /health, or the Render logs for a
        `postgresql://` connection rather than `sqlite://`), tighten this to
        cover staging too — don't leave the gap open indefinitely.
        """
        if self.ENVIRONMENT == "development":
            return self
        if self.SECRET_KEY == "dev-only-secret-change-me":
            raise ValueError(
                f"SECRET_KEY is still the development default in {self.ENVIRONMENT} — "
                f"set a real value (see .env.{self.ENVIRONMENT}.example)."
            )
        if self.ENVIRONMENT == "production" and self.DATABASE_URL.startswith("sqlite"):
            raise ValueError(
                "DATABASE_URL is SQLite in production — point it at a real "
                "Postgres instance (see .env.production.example)."
            )
        return self


settings = Settings()
