# CAPLink — Backend

**CAPLink** (Social *Capital* Link) is the licensed, multi-tenant backend connecting
university students with business partners for paid projects and internships.

Universities license CAPLink the way they'd license Blackboard or Canvas: each
institution is a tenant with its own branded portal, and its careers team controls
exactly which businesses can reach which student year-groups.

## Stack

- **FastAPI** — async-ready Python web framework
- **SQLAlchemy 2.0** — ORM (SQLite for local dev, Postgres for production)
- **JWT** (python-jose) — access + refresh tokens, mobile-friendly
- **Passlib/bcrypt** — password hashing
- **Stripe Connect** (integration point, not yet wired up — see
  `requirements-integrations.txt`) — escrow milestone payments
- **Firebase Cloud Messaging** (integration point, not yet wired up — see
  `requirements-integrations.txt`) — mobile push notifications

## Docs & demo

Everything from the planning/prototyping phase now lives in this repo under `docs/`,
not as separate downloads:

- `docs/index.html` — the university-facing licensing/sales page
- `docs/prototype.html` — the interactive click-through UI prototype (student + business views),
  with hardcoded fake data — no backend needed, just open it in a browser
- `docs/implementation-plan.md` — the original business/technical implementation plan

There's also a **live demo app** at `static/demo/app.html` — unlike the prototype above,
it's wired up to the real backend (login, matching feed, applications) and is mounted by
`app.main` at `/demo/app.html` whenever the server is running. See "Quickstart" below.

For the **full app** — nearly every endpoint, all three roles (student/business/university
admin), contracts and milestones, messaging, ratings, local business search — see
`static/app/`, mounted at `/app`, and walk through it with
[docs/deploy-locally.md](docs/deploy-locally.md).

### Hosting the static pages on GitHub Pages (github.io)

GitHub Pages only serves **static** files — it can't run the Python backend, but
`index.html` and `prototype.html` are pure HTML/CSS/JS with no backend calls, so they
work as-is:

1. Push this repo to GitHub (see below).
2. On GitHub: **Settings → Pages → Source → Deploy from a branch → `main` → `/docs`** → Save.
3. After a minute or two, it's live at `https://philipmcareavey.github.io/CAPLink/`
   (the landing page) and `https://philipmcareavey.github.io/CAPLink/prototype.html`
   (the click-through prototype).

### Hosting the live API

The FastAPI backend needs an actual Python host — GitHub Pages can't run it. The
quickest free option is **Render**:

1. On [render.com](https://render.com): **New → Blueprint**, point it at this GitHub repo.
2. Render reads `render.yaml` (included in the repo root) and provisions **both** the API
   service and a managed Postgres database (`caplink-staging-db`) automatically — `DATABASE_URL`
   is wired to it via Render's `fromDatabase`, so no manual copying of a connection string.
3. Once deployed, update `CORS_ORIGINS` (in Render's environment variables) to include your
   GitHub Pages URL so the static prototype could eventually call the real API instead of
   its hardcoded demo data.

This deploys as the `staging` environment (see below) — persistent Postgres, but still
Render's free tier. `render.yaml` also has a real **production** block, deliberately kept
commented out until an actual production launch is planned (so nothing paid/persistent gets
provisioned before anything needs it) — uncomment both the `caplink-production-db` and
`caplink-api-production` blocks together when that time comes, and reconsider their `plan:`
(free-tier Postgres isn't meant for anything persistent, and expires after a fixed period).

## Environments (development / staging / production)

`ENVIRONMENT` (in `.env` or a real env var) selects both which config file loads and which
runtime behaviour applies — set via `app/core/config.py`:

| Environment | Config file loaded | Notes |
|---|---|---|
| `development` (default) | `.env` | Sensible defaults for everything; auto-seeds demo data on first run; unhandled exceptions return full tracebacks. |
| `staging` | `.env.staging` (falls back to real env vars if the file isn't present, e.g. on a host that injects them directly) | Template: `.env.staging.example`. Render's current public deploy runs as this tier, on a real managed Postgres instance — see `render.yaml`. |
| `production` | `.env.production` (same fallback behaviour) | Template: `.env.production.example`. Doesn't exist as a live deployment yet — `render.yaml` has a ready-to-uncomment block for when it does. |

**Staging and production both refuse to start** if `SECRET_KEY` is still the development
placeholder — enforced by a validator in `Settings`, not just by convention, so a
misconfigured deploy fails loudly at startup instead of silently running with dev-grade
security. **Production additionally refuses to start on a SQLite `DATABASE_URL`**; staging
is still allowed to as a fallback for now — not because it's exempt in principle, but so
that declaring staging's Postgres database in `render.yaml` and enforcing it happen as two
separate, sequenced changes rather than one that could crash-loop the deploy if applied out
of order (see the comment on `_reject_dev_secrets_outside_dev` in `app/core/config.py`).
Copy the relevant `.env.*.example` file, fill in real values via your host's own secrets mechanism
(Render's dashboard env vars today, per `render.yaml`), and never copy secrets between
environments.

## Quickstart

**Requires Python 3.13** (not 3.14 — see note below).

### Option A — VS Code (recommended for the live demo)

1. Clone the repo and open the folder in VS Code (works the same on macOS, Windows, or Linux).
2. VS Code will offer to install the Python extension and then to create an environment /
   install `requirements.txt` — accept both prompts. (No prompt? Run **Python: Create
   Environment** from the Command Palette and pick `requirements.txt`.)
3. Open **Run and Debug** (⇧⌘D / Ctrl+Shift+D) and run **"CAPLink: Run demo (backend +
   browser)"** — this starts the API on `localhost:8000` and automatically opens
   `http://localhost:8000/demo/app.html` in your default browser.

No `.env` file or manual seeding needed — every setting has a working local default, and
the server seeds a demo university/student/business/project on first run automatically.
Log in as the student with `aisha.rahman@manchester.ac.uk` / `ChangeMe123!` (see
[docs/03-user-guide-demo-walkthrough.md](docs/03-user-guide-demo-walkthrough.md) for the
business/admin logins too).

### Option B — terminal

```bash
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt

# create demo data: a licensed university, an approved business agreement,
# a student, a business, and an open project (the VS Code option does this
# automatically on first run instead)
python -m scripts.seed_demo_data

uvicorn app.main:app --reload
```

Visit `http://localhost:8000/demo/app.html` for the live demo app, or
`http://localhost:8000/docs` for interactive Swagger docs.

An `.env` file is optional — every setting in `app/core/config.py` has a sensible local
default (SQLite, permissive CORS, etc). Copy `.env.example` to `.env` only if you want to
override something (e.g. point `DATABASE_URL` at Postgres — if so, also
`pip install -r requirements-postgres.txt`; it's not needed for the default SQLite setup,
see `requirements-postgres.txt` for why it's kept separate).

### Option C — Docker

```bash
docker-compose up
```

Builds the same `Dockerfile` a real deployment would use and runs it against a real local
Postgres container (not SQLite) — see `docker-compose.yml`'s own comments for why this is a
parity/production-sanity-check path, not the fastest day-to-day loop (Option B above still
iterates faster for everyday changes). Visit `http://localhost:8000/demo/app.html` once it's
up. **Not verified with an actual `docker build`/`docker-compose up`** — written and reviewed
carefully, but no Docker was available in the environment this was authored in; treat it as
unverified until someone actually runs it.

### Why Python 3.13, not 3.14

Python 3.14 reimplemented `typing.Union` in C, which breaks SQLAlchemy's declarative
model scanning (`app/models/*.py`) with `TypeError: descriptor '__getitem__' requires a
'typing.Union' object but received a 'tuple'` on startup — a
[known CPython 3.14 regression](https://github.com/python/cpython/issues/140348), not
something fixable from this repo's side. SQLAlchemy 2.0.51 added partial 3.14 support but
doesn't cover this case as of writing. If you already installed 3.14 (easy to do by
accident — python.org's homepage pushes the newest release by default), uninstall it and
install 3.13.x instead from https://www.python.org/downloads/ (look for a "3.13.x"
heading rather than the big top button — same on Windows and macOS). A `.python-version`
file in the repo root records this for any tooling that reads it (e.g. `pyenv`).

## Project layout

```
app/
  core/          settings, security (JWT, password hashing)
  db/            SQLAlchemy base + session
  models/        ORM models (see "Data model" below)
  schemas/       Pydantic request/response models
  services/
    access_control.py   safeguarding gate — every student<->business interaction passes through this
    matching.py          rules-based recommendation engine (Phase 1 of the matching roadmap)
    notifications.py     push notification abstraction (mobile)
  api/v1/endpoints/      one file per resource
scripts/
  seed_demo_data.py      creates a working demo tenant end-to-end
```

## The safeguarding model (core design decision)

A business has **no visibility of any student** until:

1. It holds a `UniversityBusinessAgreement` with that student's university, **and**
2. That agreement's `status` is `APPROVED`, **and**
3. The student's `band` (year group / postgrad / alumni) is in the agreement's `allowed_bands`, **and**
4. For posting projects: the project's `category` is in the agreement's `allowed_categories`.

This is enforced centrally in `app/services/access_control.py` — every endpoint that
exposes student data (shortlists, applications, messaging, project feeds) calls into
this module rather than re-implementing the rule. A university admin manages all of
this from `PATCH /api/v1/universities/{id}/business-agreements/{id}`.

## The matching engine

`app/services/matching/` is a small package, not a single file — the public contract
(`score_student_against_project`, `rank_projects_for_student`, `rank_students_for_project`)
is stable and re-exported from `app/services/matching/__init__.py`; everything else is
free to evolve behind it.

| Module | Responsibility |
|---|---|
| `skills.py` | Skill normalisation (synonym table: "React.js"/"reactjs" → "react") + fuzzy matching (`difflib`) for typos/unlisted abbreviations, with partial credit for near-misses |
| `text_similarity.py` | Dependency-free TF-IDF + cosine similarity between a project brief and a student's declared background — catches semantic overlap that skill-tag matching alone misses |
| `degree.py` | Degree-relevance scoring with a strong/supporting keyword taxonomy (an Economics student gets partial credit for data roles, not zero) |
| `reputation.py` | Bayesian-shrunk rating score (a single 5★ doesn't outrank a 20-project 4.8★ track record) + rate-compatibility and availability heuristics |
| `collaborative.py` | **Real** DB-backed Phase-2 signal: looks at `Application`/`StudentProfile` history for similar-skilled students who succeeded on similar-category projects. Returns `None` (not 0) when there's not yet enough data — a genuine "no signal" is different from a genuine "bad fit" |
| `scorer.py` | Orchestrates all of the above with **dynamic weight renormalization**: any factor that can't be computed (e.g. no collaborative data yet) is excluded entirely and its weight redistributed across the rest, rather than silently zeroed |
| `config.py` | `MatchWeights` — tunable per call, so different weight profiles can be A/B tested without code changes |

Every recommendation shown is written to `RecommendationLog`, including the plain-English
reasons and a full per-factor breakdown (raw score, applied weight, contribution) available
via `GET /api/v1/projects/{id}/match-explanation` — this is the training data Phase 3
(embedding-based semantic matching) will consume later, and it's also just a good "why
was I shown this?" UI feature and a debugging tool for tuning weights.

### Running the matching engine's tests

```bash
pip install -r requirements.txt -r requirements-dev.txt --break-system-packages
pytest tests/ -v
```

Covers: skill normalisation/fuzzy-matching edge cases, TF-IDF similarity sanity checks,
reputation shrinkage behaviour, degree-relevance tiers, full end-to-end scoring + ranking
order, custom-weight behaviour, and DB-backed collaborative-filtering integration tests
(using an in-memory SQLite session, see `tests/conftest.py`).

## Mobile-specific adjustments

- **Refresh tokens**: `POST /api/v1/auth/refresh` mints new access tokens from a
  long-lived refresh token stored in secure device storage, avoiding frequent re-logins.
- **Pagination everywhere**: list endpoints (e.g. `/projects/feed`) take `page` /
  `page_size` query params (capped at 50) so mobile clients never pull an unbounded feed.
- **Device registration & push**: `POST /api/v1/mobile/devices` registers an
  iOS/Android push token; `app/services/notifications.py` fans out new-match,
  message, payment, and rating events. Swap the placeholder `_send_push` for a real
  `firebase_admin.messaging.send()` call once Firebase credentials are configured.
- **Combined home payload**: `GET /api/v1/mobile/home` returns a single trimmed
  summary object instead of requiring 4-5 separate calls — matters more on cellular data.
- **CORS**: pre-configured to accept `capacitor://localhost` / custom native schemes
  in addition to standard web origins (see `.env.example`).

## Postcode-radius local business search

`GET /api/v1/universities/{id}/local-businesses?radius_miles=10` — "degree-relevant
businesses within N miles of my campus." Built to reuse existing pieces rather than
duplicate logic:

- **Safeguarding still applies**: only businesses with an `APPROVED` agreement covering
  the student's band are eligible at all — radius search is a filtered *view* over the
  same safeguarding-gated pool as the project feed, never a bypass of it.
- **Degree relevance reuses the matching engine's scorer** (`app/services/matching/degree.py`)
  — "relevant to your degree" means the same thing here as it does when ranking projects.
- **Geocoding**: `app/services/geo.py` wraps [postcodes.io](https://postcodes.io) (free,
  no API key, UK-only — matches CAPLink's initial market). A business sets its postcode via
  `PATCH /api/v1/businesses/me`; a university admin sets the campus centre-point via
  `PATCH /api/v1/universities/{id}/location`. Both are geocoded once and cached
  (`latitude`/`longitude` columns) rather than re-geocoded per search — radius search is a
  pure Haversine-distance calculation over already-known coordinates, so it stays fast.
- A business that never sets a postcode (e.g. fully remote) simply never appears in radius
  results — that's correct behaviour, not an error state.

Results are sorted by degree relevance first, distance as the tiebreaker — a highly
relevant business 8 miles out ranks above a barely-relevant one 2 miles out, since a
"local search" for a student is really "give me relevant options nearby," not a pure
distance sort.

## University licensing endpoints

- `POST /api/v1/universities` (platform-admin only) — onboard a new licensed institution
- `GET /api/v1/universities/{slug}/public` — unauthenticated branding lookup, powers each
  university's landing page at `{slug}.caplink.io`
- `PATCH /api/v1/universities/{id}/location` (university-admin) — set/refresh campus postcode
- `PATCH /api/v1/businesses/me` — a business sets its postcode (enables radius search) and other profile fields
- `POST /api/v1/universities/{id}/business-agreements` — a business requests access
- `PATCH /api/v1/universities/{id}/business-agreements/{agreement_id}` — a university
  admin approves/restricts access (bands, categories, project-review requirement)

## What's stubbed vs. production-ready

Fully implemented: auth, multi-tenant licensing, safeguarding access control, rules-based
matching + recommendation logging, applications, contracts/milestones, mutual blind
ratings, messaging with off-platform-contact flagging, mobile device registration,
Alembic-managed schema migrations, structured JSON logging, CI (lint/type-check/test).

Integration points left as clearly-marked placeholders (each notes what to replace):
Stripe PaymentIntent creation/capture, Firebase push delivery, university-email domain
verification is currently a simple string match (swap for a real SSO/Shibboleth flow
for enterprise customers), Sentry error tracking is wired up but inactive without a real
`SENTRY_DSN`, and uptime monitoring isn't configured anywhere (see "Observability" above).

## Database migrations (Alembic)

Schema changes go through Alembic, not `Base.metadata.create_all` — `app/db/migrations.py`
runs the migration chain automatically on every startup (`alembic/versions/`), so a fresh
clone still needs zero manual steps. When you change a model:

```bash
alembic revision --autogenerate -m "describe the change"
```

Review the generated file in `alembic/versions/` before committing — autogenerate is a
strong first draft, not infallible (it won't detect a plain column rename, for instance;
that shows up as a drop + add unless you edit the migration by hand). The next app startup
(or `alembic upgrade head` directly) applies it.

A database that already has every current table but no `alembic_version` row (i.e. it
predates Alembic being wired up) gets stamped as already being at the latest migration
instead of replaying `CREATE TABLE`s that would just fail on "already exists" — this is
what let the switchover happen without anyone needing to drop and reseed an existing
local `caplink.db`.

## Observability

**Structured logging** — every log line, including uvicorn's own request/access/error
logs (not just the app's own `logger.info(...)` calls), comes out as one JSON object per
line, with real separate fields rather than everything crammed into a message string —
see `app/core/observability.py`. Per-request logs (method, path, status code, duration)
come from `RequestLoggingMiddleware` in `app/main.py`, replacing uvicorn's own plain-text
access log rather than duplicating it. Set `LOG_LEVEL` (default `INFO`, `.env.example`
uses `DEBUG` for local dev) to control verbosity per environment.

One gotcha worth knowing if this ever needs touching again: Alembic's `env.py` calls
`logging.config.fileConfig(alembic.ini)` as a side effect of loading, which resets the
*entire* root logger (level, handlers) to `alembic.ini`'s own plain-text config — `app/db/
migrations.py`'s `run_migrations()` saves and restores the root logger's state around the
Alembic call specifically so this doesn't leak out and silently break the app's own
logging every time migrations run (including the second, redundant call inside
`scripts/seed_demo_data.py`).

**Error tracking (Sentry)** — inactive by default; set `SENTRY_DSN` to a real DSN to turn
it on (see `.env.production.example`). This needs an actual Sentry account and project —
sentry.io has a free tier, but nothing in this repo can create the account for you.
Exceptions are captured explicitly from the global exception handler in `app/main.py`
(rather than relying only on Sentry's own auto-instrumentation), since that handler
already catches everything and returns a clean JSON error response — a well-behaved
error handler like that means an exception never "escapes" in the way generic
auto-instrumentation typically looks for.

**Uptime monitoring** — not configured; this is 100% an external step, there's nothing to
add to this repo for it. Recommended: a free monitor (e.g. [UptimeRobot](https://uptimerobot.com))
polling `https://<your-render-url>/health` every 5 minutes with email/SMS alerting on a
non-200 response. `/health` deliberately does nothing but confirm the process is up and
responding — it doesn't check the database connection, so a monitor on it alone won't
catch "app is up but the database is unreachable"; that failure mode currently only shows
up as request-level 500s in the logs/Sentry above.

## Continuous integration

`.github/workflows/ci.yml` runs three independent checks on every pull request (and on
pushes to `main`, as a safety net): `ruff check .` (lint), `mypy app/ scripts/`
(type-check), and the full `pytest` suite. Config for the first two lives in
`pyproject.toml` — notably `line-length = 135` (matches this codebase's existing style
rather than forcing a repo-wide reformat) and a deliberately narrow `select = ["E", "F"]`
(flake8-bugbear's `B008` would otherwise flag every single FastAPI `Depends(...)` default
argument as an anti-pattern, which is just how FastAPI dependency injection works).

## Rollback procedure

**Application code**: Render redeploys automatically on every push to `main` (see
`render.yaml`). To roll back a bad deploy, either:
- In the Render dashboard, open the service's **Events**/**Deploys** history and redeploy
  a previous successful commit, or
- `git revert <bad-commit-sha>` and push — safer than `git reset` since it doesn't rewrite
  history other clones/CI may already have.

**Database schema**: `alembic downgrade -1` reverses the most recently applied migration
(or `alembic downgrade <revision>` for a specific one). Known limitation: the baseline
migration's `downgrade()` drops tables but not the Postgres `ENUM` types those columns
use, so a downgrade-then-upgrade cycle against real Postgres would hit "type already
exists" — not an issue for the normal `stamp`-or-`upgrade` path the app itself uses (see
`app/db/migrations.py`), only for a deliberate manual downgrade.

Application code and schema rollbacks are independent — reverting a commit does not
automatically downgrade the database, and vice versa. If a bad deploy included both a
code change and a migration, roll back both, in that order (schema first, since old code
generally can't run against a newer schema, but new-schema-old-code mismatches are more
likely to actually break something than the reverse).
