"""Technical Implementation Plan 1.c.iv — latency dashboards for key
endpoints. See app/core/latency_metrics.py's own docstring for why an
in-process rolling window is a genuinely usable answer to this step given
this project's actual (single-instance, no APM tool) deployment today,
not a placeholder standing in for one.
"""
from app.core.security import hash_password
from app.models.enums import UserRole
from app.models.user import User

from tests.test_golden_path_e2e import _auth


def _make_platform_admin_token(client, *, email="latency-admin@caplink.internal", password="Correct-Horse-Battery-Lat-1"):
    db = client.db_sessionmaker()
    try:
        db.add(
            User(
                email=email,
                hashed_password=hash_password(password),
                role=UserRole.PLATFORM_ADMIN,
                full_name="Latency Admin",
                is_email_verified=True,
            )
        )
        db.commit()
    finally:
        db.close()
    login = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert login.status_code == 200, login.text
    return login.json()["access_token"]


def test_latency_dashboard_aggregates_by_route_template_not_raw_path(client):
    admin_token = _make_platform_admin_token(client)

    # Two calls to the *same* route template with different path params —
    # these must aggregate under one key, not fragment per real id.
    client.get("/api/v1/universities/does-not-exist-1/public")
    client.get("/api/v1/universities/does-not-exist-2/public")

    dashboard = client.get("/api/v1/observability/latency-dashboard", headers=_auth(admin_token))
    assert dashboard.status_code == 200, dashboard.text
    data = dashboard.json()

    key = "GET /universities/{slug}/public"
    assert key in data["endpoints"], data["endpoints"]
    entry = data["endpoints"][key]
    assert entry["count"] == 2
    assert entry["p50_ms"] >= 0
    assert entry["avg_ms"] >= 0


def test_latency_dashboard_requires_platform_admin(client):
    forbidden = client.get("/api/v1/observability/latency-dashboard")
    assert forbidden.status_code in (401, 403), forbidden.text
