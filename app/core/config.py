"""
CAPLink — central configuration.

Reads from environment variables / .env. See .env.example for the full list.
CAPLink is a licensed, multi-tenant platform: each university is a *tenant*
with its own branding, subdomain, and safeguarding policies, but all tenants
share this single backend deployment.
"""
from typing import List

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", case_sensitive=False, extra="ignore")

    APP_NAME: str = "CAPLink"
    ENVIRONMENT: str = "development"

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


settings = Settings()
