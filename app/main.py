"""
CAPLink — Social Capital Link
==============================
Backend entrypoint. Run locally with:

    uvicorn app.main:app --reload

This creates SQLite tables automatically on startup for quick local
development (see .env.example — point DATABASE_URL at Postgres for
staging/production and manage schema changes with Alembic instead).
"""
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

import app.models  # noqa: F401 — ensures all models register with Base.metadata
from app.api.v1.api import api_router
from app.core.config import settings
from app.db.base_class import Base
from app.db.session import engine

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

# Reference demo UI — a plain HTML/JS page (no build step) demonstrating what
# a student/business/university-admin would actually see, calling this same
# API same-origin. Not part of the product; see docs/04-using-the-api-docs-ui.md.
app.mount("/demo", StaticFiles(directory="static/demo", html=True), name="demo")
