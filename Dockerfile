# Technical Implementation Plan step 1.d.i. Not verified with an actual
# `docker build`/`docker run` — no Docker available in the environment this
# was written in. Every dependency here already resolves to a pre-built
# wheel on Debian/Linux + Python 3.13 (confirmed via Render's own build
# logs — see CLAUDE.md), which is what python:3.13-slim also is, but this
# still needs a real build/run before being trusted for a real deploy.
FROM python:3.13-slim

# Same reasoning as requirements-postgres.txt's own comment: psycopg2-binary
# ships a self-contained wheel, so no libpq-dev / build-essential needed
# here the way a source build would require.
WORKDIR /app

COPY requirements.txt requirements-postgres.txt ./
RUN pip install --no-cache-dir -r requirements.txt -r requirements-postgres.txt

COPY app/ ./app/
COPY alembic/ ./alembic/
COPY alembic.ini ./
COPY scripts/ ./scripts/
COPY static/ ./static/

# Runs as non-root — a Cyber Essentials baseline expectation (Technical
# Implementation Plan step 2.d), cheap to do from day one rather than
# retrofit later.
RUN useradd --create-home --shell /bin/bash caplink
USER caplink

EXPOSE 8000

# Shell form (not exec form) deliberately, so $PORT actually expands —
# matches render.yaml's own startCommand, which relies on Render injecting
# $PORT the same way. Migrations run automatically on startup regardless of
# how this container is invoked (see app/main.py's on_startup hook), so
# there's no separate migrate step needed here.
CMD uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}
