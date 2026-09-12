"""
CAPLink — Social Capital Link
==============================
Backend entrypoint. Run locally with:

    uvicorn app.main:app --reload

Applies the Alembic migration chain (alembic/versions/) automatically on
startup — a fresh SQLite file gets every table with zero manual steps for
local dev, and the same mechanism applies cleanly to Postgres once a real
staging/production instance exists. See app/db/migrations.py.
"""
import logging
import time
import uuid
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from starlette.middleware.base import BaseHTTPMiddleware

from app import models  # noqa: F401 — ensures all models register with Base.metadata
from app.api.v1.api import api_router
from app.core import latency_metrics
from app.core.body_limit import MaxBodySizeMiddleware
from app.core.config import settings
from app.core.observability import configure_error_tracking, configure_logging
from app.core.rate_limit import limiter
from app.core.security_headers import HSTSMiddleware
from app.db.migrations import run_migrations
from app.db.session import SessionLocal, engine
from app.models.university import University

REPO_ROOT = Path(__file__).resolve().parent.parent
request_logger = logging.getLogger("caplink.request")


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """One structured JSON line per request — method/path/status/duration as
    real, separate fields (not text baked into a message string), replacing
    uvicorn's own plain-text access log rather than duplicating it (see
    configure_logging, which silences uvicorn.access's own handler)."""

    async def dispatch(self, request: Request, call_next):
        request_id = str(uuid.uuid4())
        started_at = time.monotonic()
        response = await call_next(request)
        duration_ms = round((time.monotonic() - started_at) * 1000, 2)
        request_logger.info(
            "request",
            extra={
                "request_id": request_id,
                "method": request.method,
                "path": request.url.path,
                "status_code": response.status_code,
                "duration_ms": duration_ms,
            },
        )
        # Technical Implementation Plan 1.c.iv — the route's *template*
        # path (e.g. "/projects/{project_id}/shortlist"), not the raw
        # per-request path with real IDs in it, so every call to the same
        # endpoint aggregates together. `request.scope["route"]` is only
        # populated once routing has actually matched a route, which
        # happens inside call_next — never available before it.
        route = request.scope.get("route")
        endpoint_key = f"{request.method} {route.path}" if route is not None else f"{request.method} {request.url.path}"
        latency_metrics.record_duration(endpoint_key, duration_ms)
        response.headers["X-Request-ID"] = request_id
        return response


app = FastAPI(
    title=settings.APP_NAME,
    description="Licensed platform connecting university students with vetted business partners "
    "for paid projects and internships, with university-controlled safeguarding policies.",
    version="0.1.0",
)

# Per-IP rate limiting (Technical Implementation Plan step 2.a.ii) — the
# actual Limiter instance lives in app/core/rate_limit.py, not here, since
# endpoint modules applying @limiter.limit(...) are imported *by* this
# module (via api_router below); importing it back from here would be a
# circular import.
app.state.limiter = limiter
# slowapi's handler is typed Callable[[Request, RateLimitExceeded], Response],
# narrower than add_exception_handler's Callable[[Request, Exception], ...] —
# a real Exception subclass at runtime, just a stub mismatch between the two
# libraries, not an actual type error in this code.
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)  # type: ignore[arg-type]

# CORS: web dashboard + mobile app origins (capacitor://, ionic://, custom schemes)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
# Added after CORS so it wraps outermost — captures the full request
# lifecycle (including CORS handling) and the final status code.
app.add_middleware(RequestLoggingMiddleware)
# Oversized-payload hardening (2.c.ii) — rejects any body over the cap
# before it reaches routing/Pydantic validation. Starlette's add_middleware
# actually makes the *most recently added* middleware the *outermost* layer
# (each call inserts itself before the others in the stack it builds), so
# adding this last puts it right after ServerErrorMiddleware — as early as
# possible, ahead of CORS/logging/routing, closest to the raw ASGI request.
app.add_middleware(MaxBodySizeMiddleware, max_bytes=settings.MAX_REQUEST_BODY_BYTES)
# HSTS (7.d.ii) — only outside development; see security_headers.py's
# module docstring for why localhost/no-TLS dev shouldn't get this header.
if settings.ENVIRONMENT != "development":
    app.add_middleware(HSTSMiddleware)


@app.on_event("startup")
def on_startup():
    # Reconfigures logging (and Sentry, if SENTRY_DSN is set) here rather
    # than at module import time: uvicorn does its own logging setup between
    # importing this module and firing the ASGI lifespan startup event, so
    # doing it here is what lets this override uvicorn's own formatters
    # rather than being overridden by them.
    configure_logging(settings.LOG_LEVEL)
    configure_error_tracking(settings.SENTRY_DSN, settings.ENVIRONMENT)

    run_migrations(engine)

    # First run in a fresh clone: no .env, no data yet — seed the demo
    # university/student/business/project automatically so the Bridge demo
    # (mounted below at /demo) has something to show immediately. Guarded by
    # ENVIRONMENT so a real deployment with its own .env never auto-seeds.
    if settings.ENVIRONMENT == "development":
        db = SessionLocal()
        try:
            if db.query(University).first() is None:
                from scripts.seed_demo_data import run as seed_demo_data

                seed_demo_data()
        finally:
            db.close()


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    # Never leak stack traces to mobile/web clients in production
    if settings.ENVIRONMENT == "development":
        raise exc
    request_logger.error("unhandled_exception", exc_info=exc, extra={"path": request.url.path})
    if settings.SENTRY_DSN:
        import sentry_sdk

        sentry_sdk.capture_exception(exc)
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})


@app.get("/health", tags=["meta"])
def health_check():
    """Confirms the process is up and which environment it's running in.
    Does not check database connectivity — a DB outage surfaces as
    request-level 500s/Sentry errors, not a failed health check."""
    return {"status": "ok", "app": settings.APP_NAME, "environment": settings.ENVIRONMENT}


# The bare root URL had no route at all — anyone visiting
# https://caplink-api.onrender.com directly (rather than a specific
# /demo or /app link) hit a raw {"detail":"Not Found"}. /demo/index.html
# is the intended public entry point (the marketing-style landing page,
# with its own links into /app), so redirect there rather than leaving
# the root a dead end.
@app.get("/", include_in_schema=False)
def root():
    return RedirectResponse(url="/demo/index.html")


app.include_router(api_router, prefix="/api/v1")

# Bridge demo UI (static/demo/index.html + app.html) — served from the same
# origin as the API so its relative fetch("/api/v1/...") calls just work,
# no CORS setup needed. Visit /demo/app.html once the server is running.
app.mount("/demo", StaticFiles(directory=REPO_ROOT / "static" / "demo", html=True), name="demo")

# The fuller reference app (static/app/) — exercises nearly the whole API
# across all three roles (student/business/university admin), same
# same-origin trick as /demo. /demo stays as the lightweight teaser; this is
# the one to actually explore the platform with. See docs/deploy-locally.md.
app.mount("/app", StaticFiles(directory=REPO_ROOT / "static" / "app", html=True), name="app")
