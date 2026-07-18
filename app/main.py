"""
CAPLink — Social Capital Link
==============================
Backend entrypoint. Run locally with:

    uvicorn app.main:app --reload

This creates SQLite tables automatically on startup for quick local
development (see .env.example — point DATABASE_URL at Postgres for
staging/production and manage schema changes with Alembic instead).
"""
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

import app.models  # noqa: F401 — ensures all models register with Base.metadata
from app.api.v1.api import api_router
from app.core.config import settings
from app.db.base_class import Base
from app.db.session import SessionLocal, engine
from app.models.university import University

REPO_ROOT = Path(__file__).resolve().parent.parent

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


@app.on_event("startup")
def on_startup():
    Base.metadata.create_all(bind=engine)

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
