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
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.base import BaseHTTPMiddleware

from app import models  # noqa: F401 — ensures all models register with Base.metadata
from app.api.v1.api import api_router
from app.core.config import settings
from app.core.observability import configure_error_tracking, configure_logging
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
        response.headers["X-Request-ID"] = request_id
        return response


app = FastAPI(
    title=settings.APP_NAME,
    description="Licensed platform connecting university students with vetted business partners "
    "for paid projects and internships, with university-controlled safeguarding policies.",
    version="0.1.0",
)

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
    return {"status": "ok", "app": settings.APP_NAME, "environment": settings.ENVIRONMENT}


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
