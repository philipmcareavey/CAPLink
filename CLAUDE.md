# CLAUDE.md — orientation for whoever (human or agent) works on this repo next

**Standing rule established the hard way in this session — do not repeat
this mistake**: completing an epic's code, verifying it, and even pushing
it is not "done" until `../CAPLink-Technical-Tracker.xlsx` (both the
`Tracker` rows *and* the `Dashboard` sheet's cached formula values) and
**both** `CLAUDE.md` files are updated to reflect it. The user explicitly
caught this being skipped once ("You haven't updated the tracker") after
Epic 2.a's code was fully done and pushed — treat the tracker/CLAUDE.md
update as a mandatory last step of every epic, not optional cleanup.

This file exists so a new session doesn't have to re-derive context by
reading every file. Read this first; it links to the deeper docs instead of
repeating them.

## What this project is

CAPLink — a licensed, multi-tenant FastAPI backend connecting university
students with business partners for paid projects/internships. Full
plain-English explanation: [docs/05-explain-it-simply.md](docs/05-explain-it-simply.md).
Architecture/module tour: [docs/01-project-structure.md](docs/01-project-structure.md).
Everything else (running it, the matching engine internals, licensing
endpoints, what's stubbed vs. real) is documented in [README.md](README.md) —
that file is kept up to date and is the primary source of truth.

## Where the code actually came from (matters for future merges)

This repo's history is short and doesn't tell the whole story:
1. Initial commit was an earlier, simpler version of the backend.
2. A separate, more advanced local copy (newer matching engine as a package,
   geo-based local search, a full pytest suite) got merged in on top —
   `git log --oneline` shows this as "Merge caplink 4 backend updates...".
   If another such external copy shows up again, diff it against the repo
   with `.git`/`.env`/`__pycache__`/`venv`/`caplink.db`/`.DS_Store` excluded
   before copying anything over — those are the only things that reliably
   differ incidentally.
3. Everything since has been onboarding/reliability polish (below), not
   feature work.

## Current state (as of the last session)

- Pushed to a **public** GitHub repo: `git@github.com:philipmcareavey/CAPLink.git`,
  branch `main`. Push access from this Mac is via a dedicated SSH key at
  `~/.ssh/id_ed25519_github` (added to the account's SSH keys), configured in
  `~/.ssh/config` for `github.com`.
- The repo has **two** local git identities worth knowing: this Mac's global
  git config had no `user.name`/`user.email` set, so it was set locally in
  this repo only, using the account owner's email.
- A live demo app (`static/demo/index.html` + `app.html`, calls the real API
  via relative `fetch('/api/v1/...')`) exists but wasn't wired up when found —
  `app/main.py` now mounts it at `/demo` so it's actually reachable, and
  auto-seeds demo data on first startup in `development` mode so a fresh
  clone needs zero manual setup.
- VS Code is the intended zero-friction path: `.vscode/launch.json` has a
  "CAPLink: Run demo (backend + browser)" config that starts uvicorn and
  auto-opens `/demo/app.html` in the browser (via `serverReadyAction`).
  `.vscode/settings.json` pins the default interpreter to `./venv` — added
  because VS Code was otherwise defaulting to a system Python without the
  project's packages installed ("No module named uvicorn").
- [docs/very simple explanation for very simple man (dadster).md](<docs/very simple explanation for very simple man (dadster).md>)
  is a from-scratch, zero-jargon walkthrough (install Git/Python/VS Code →
  clone via VS Code's UI → press Run → browser opens) written for the
  account owner's dad, who has never used a programming tool before. Every
  step links to a matching entry in that file's own Troubleshooting section.
  **If you fix a new setup/install failure, add both**: a step-pointer and a
  troubleshooting entry there, matching the existing pattern — that's an
  explicit standing preference from the user, not a one-off.

## The full app (`/app`), alongside the lightweight demo (`/demo`)

`static/demo/` (mounted at `/demo`) only ever covered a slice of the API, and
two of its business-side calls (`GET /projects/mine`, `GET
/projects/{id}/applications`) referenced endpoints that didn't exist post-merge
— that part of the demo was silently broken. `static/app/` (mounted at `/app`,
same same-origin trick as `/demo`) is the fuller build: nearly the entire API,
all three roles, native ES modules per concern (`js/api.js`, `js/dom.js`,
`js/constants.js`, `js/main.js`, `js/student.js`, `js/business.js`,
`js/university-admin.js`, `js/shared/contracts.js`, `js/shared/messaging.js`)
rather than one growing HTML file — no bundler, since same-origin `<script
type="module">` just works when served by `StaticFiles`. Walkthrough:
[docs/deploy-locally.md](docs/deploy-locally.md).

Building it required 5 new backend GET endpoints that plain didn't exist
before (own projects, real applicants vs. ranked candidates, own contracts
role-aware, own message threads, own rating history both directions) — see
each endpoint's docstring for the exact shape, or `docs/deploy-locally.md`'s
closing section for the short version. All were verified both via curl
against the seeded accounts and by actually clicking through every tab of
`/app` in a real browser (Chrome via the claude-in-chrome extension) for all
three roles, including a full contract → milestone → rating lifecycle and a
flagged-message exchange — not just an import/syntax check.

## Technical Implementation Plan progress (Workstream 1 9/16, Workstream 2 12/16, 2026-08-30–09-06)

`../CAPLink-Technical-Implementation-Plan.docx` (one level up, not in this
repo) and its companion `../CAPLink-Technical-Tracker.xlsx` define a 104-step
productionization backlog — see the top-level `CLAUDE.md` for the full
breakdown. Step **1.a.i "Create separate dev/staging/production environment
configurations"** is now done:

- `app/core/config.py`'s `Settings` now types `ENVIRONMENT` as
  `Literal["development", "staging", "production"]` and resolves which env
  file to load *before* the class is built (`_ENV_FILE`), since
  pydantic-settings fixes `env_file` at class-definition time: `development`
  keeps loading plain `.env` (unchanged, zero-friction default); `staging`/
  `production` look for `.env.staging` / `.env.production` and fall back to
  whatever the process environment already provides if no such file exists
  on disk — this matches how the current Render deploy already works
  (`render.yaml` injects env vars directly, no `.env` file shipped).
- A `model_validator` on `Settings` now **refuses to boot** in staging/production
  if `SECRET_KEY` is still the dev placeholder, and **refuses to boot in
  production specifically** (not staging — see 1.a.ii below for why) if
  `DATABASE_URL` is still `sqlite://`. Verified all paths manually (dev
  unaffected, staging fails loudly on bad config then succeeds with real
  values via env vars, production auto-loads a `.env.production` file) —
  see the tracker's Notes column on row 1.a.i for the original verification
  commands.
- Added `.env.staging.example` and `.env.production.example` (git-tracked
  templates); added `.env.staging` / `.env.production` (the *real*,
  filled-in files, if anyone creates them locally) to `.gitignore` alongside
  the existing `.env` entry.
- `README.md` gained an "Environments" section explaining the above.
- Ran the full test suite before/after: **1 pre-existing failure**
  (`tests/test_collaborative.py::test_scorer_includes_collaborative_factor_when_db_and_data_available`)
  present on `main` before this change too (confirmed via `git stash`) — not
  caused by this work, left alone rather than scope-creeping into an
  unrelated matching-engine fix.
- The Tracker spreadsheet was updated directly (row 1.a.i → Done, 100%, with
  a Notes entry) by hand-editing its underlying XML (`.xlsx` is a zip of XML
  parts — no `openpyxl`/`pandoc` available in this environment) rather than
  through Excel/LibreOffice (neither installed here). A pre-edit backup was
  kept at `/tmp/CAPLink-Technical-Tracker.xlsx.backup` in case anything looks
  wrong when actually opened in Excel — the zip and every XML part validate
  and re-parse correctly, and the Dashboard sheet's cached formula values
  were hand-updated to match (1/104 done overall, 1/16 for Workstream 1,
  1/54 for P0), but it hasn't been opened in a real spreadsheet app to
  confirm it *looks* right, since none was available to test with.

**Step 1.a.ii "Migrate secrets to a managed secrets store" — in progress
(75%), not fully done:**

- `render.yaml`'s `SECRET_KEY` already used Render's `generateValue: true` —
  generated and stored by Render itself, never in git or a file. That alone
  satisfies the step for the one secret that matters most.
- Added `STRIPE_SECRET_KEY` / `STRIPE_WEBHOOK_SECRET` / `FIREBASE_CREDENTIALS_JSON`
  to `render.yaml` as `sync: false` — Render's mechanism for "this service
  needs this var, a human sets its value once in the dashboard, it's never
  in the blueprint or git." Same principle Doppler/AWS Secrets Manager would
  give; fine to keep using Render's own version of it while there's a single
  host and neither integration is live yet.
- **What's genuinely blocked, not just deferred**: "DB credentials" per the
  step's own wording can't be migrated because none exist yet — the only
  live deployment still runs SQLite (see below), so there's no real
  Postgres connection string anywhere to move into a secrets store. That
  part of this step is effectively gated on 1.a.iv.
- **Found and fixed a regression from 1.a.i while doing this**:
  `render.yaml` had `ENVIRONMENT=production` with a hardcoded SQLite
  `DATABASE_URL` — combined with 1.a.i's new validator, the *next* deploy of
  the existing Render service would have crashed at startup. Fixed by (a)
  relabelling that service `ENVIRONMENT=staging` in `render.yaml`, since
  it's genuinely Render's free/ephemeral tier used for public demoing, not
  real production, and (b) narrowing the SQLite rejection in `Settings` to
  `production` only, since no staging Postgres instance exists yet either
  (1.a.iv). Production still hard-rejects SQLite; staging is allowed to for
  now. **Tighten this to cover staging too once 1.a.iv lands** — don't leave
  it loose indefinitely.
- Verified all 5 combinations (dev; staging+sqlite+real-secret passes —
  this is the actual Render config now; staging+dev-secret fails;
  production+sqlite fails even with a real secret; production+postgres+real-secret
  passes) and reran the full test suite (same 1 pre-existing unrelated
  failure, nothing new broken).
- `.env.staging.example`, `.env.production.example`, and README's
  Environments section updated to match the production-only SQLite rule.

**Step 1.a.iii "Introduce Alembic for schema migrations" — done:**

- `alembic init alembic`, then wired `alembic/env.py` to import `app.models`
  (registers everything on `Base.metadata`) and read
  `app.core.config.settings.DATABASE_URL` directly — migrations always
  target the same database the app itself would use for the current
  `ENVIRONMENT`, never a second hand-maintained connection string.
  `alembic.ini`'s `sqlalchemy.url` is a deliberately-unused placeholder now
  (comment explains why); `script_location` is set to an absolute path in
  code too, so it doesn't depend on CWD.
- Autogenerated the baseline migration
  (`alembic/versions/bb371d385f9a_baseline_schema.py`) against a fresh empty
  DB — captures all 15 tables/indexes/FKs exactly as `create_all` used to.
  Verified `upgrade head` → `downgrade base` → `upgrade head` all work
  cleanly.
- New `app/db/migrations.py:run_migrations(engine)` replaces the
  `Base.metadata.create_all(bind=engine)` calls in both `app/main.py`'s
  startup hook and `scripts/seed_demo_data.py`. It's not a plain
  `alembic upgrade head` though — a database that already has every table
  but no `alembic_version` row (this Mac's own `caplink.db`, Render's
  existing staging deploy, anyone else's pre-existing local copy) would hit
  "table already exists" and crash on a naive upgrade, since it predates
  Alembic being wired up at all. `run_migrations` detects that case (tables
  exist, no `alembic_version`) and runs `alembic stamp head` instead —
  records the DB as already being at the baseline without replaying any DDL.
  A genuinely fresh DB (new clone, CI, a future Postgres instance) still
  gets a real `upgrade head`, so the zero-setup fresh-clone experience is
  unchanged.
- **Verified against three real scenarios, not just the fresh-DB case**:
  (1) a brand new DB — creates schema + demo-seeds normally; (2) a
  simulated legacy DB (tables via the old `create_all` path, no
  `alembic_version`) — stamps cleanly, no crash; (3) **this Mac's actual
  `caplink.db`** (backed up first to `/tmp/caplink.db.backup-before-alembic`)
  — stamped cleanly, row counts for `universities`/`users`/`student_profiles`/
  `business_profiles`/`projects` confirmed identical before and after, and a
  second run (already-migrated path) was a clean no-op. Full test suite
  rerun too: same 1 pre-existing unrelated failure, nothing new broken.
- README gained a "Database migrations (Alembic)" section (how to add one:
  `alembic revision --autogenerate -m "..."`, review before committing,
  autogenerate doesn't detect plain renames). `docs/01-project-structure.md`
  and README's stubbed-features lists both updated — Alembic is no longer
  stubbed.

**Step 1.a.iv "Stand up separate staging and production Postgres instances"
— DONE for staging, confirmed live 2026-08-30.** `caplink-staging-db` is a
real, running Render Postgres instance, and `caplink-api` is genuinely
reading/writing to it (confirmed via Render's deploy logs: `Context impl
PostgresqlImpl` and `Running upgrade -> bb371d385f9a, baseline schema`,
service live at `caplink-api.onrender.com`). This also closed out the rest
of **step 1.a.ii's "DB credentials"** requirement (now also marked Done) —
the real connection string exists only in Render's dashboard, never in git.

I had no Render account access and no local Docker/Postgres in this
environment, so I could only prepare `render.yaml` — the user did the
actual dashboard work (creating/recreating the database, pasting the
connection string) themselves, live, over several back-and-forth rounds.
Two real gotchas came up, both now documented in `render.yaml`'s own
comments so they don't get rediscovered the hard way again:

1. **Region mismatch.** `render.yaml`'s first version didn't set `region:`
   on `caplink-staging-db`, so Render defaulted it to Ohio while
   `caplink-api` was actually in Oregon (I'd initially guessed the opposite
   way round and got it wrong first). Render's internal `dpg-...` hostnames
   only resolve between services in the *same* region, so every deploy
   failed at startup with `could not translate host name` — not a timing
   issue, not a code bug, purely a region mismatch. Fixed by recreating the
   database in Oregon and adding `region: oregon` explicitly (also applied
   to the commented-out production scaffold, which should be re-verified
   when it's ever uncommented for real).
2. **`fromDatabase` doesn't re-resolve on a Manual Deploy.** After fixing
   the region, `DATABASE_URL` kept resolving to the *old, now-deleted*
   database's hostname — the exact same one, deploy after deploy. Render
   only re-resolves a `fromDatabase`-linked env var during an actual
   Blueprint **Sync**, not a plain "Deploy latest commit." The working fix
   was pasting the new database's Internal Database URL directly into
   `caplink-api`'s Environment tab by hand. `render.yaml` still declares the
   `fromDatabase` link (it's the correct infra-as-code intent, and should
   auto-work on a future real Sync), but know that a manual override is
   sitting on top of it right now — don't assume the file and reality
   agree without checking the dashboard.

**Also discovered, unrelated to either gotcha above but worth a permanent
note**: partway through debugging, the user's real staging database
password ended up pasted into their local, gitignored `.env` (not `.git`-
tracked, never reached the public repo, but real local exposure). Worth
checking next session whether it's still there — local dev should only
ever point at its own default SQLite, never a real environment's secret.

**Now genuinely done, not just prepared**: the SQLite-rejection validator
in `app/core/config.py` covers **both staging and production** as of this
session — the temporary staging exemption from 1.a.i/1.a.ii is gone.

**Still open, lower priority**: PgBouncer connection pooling (a manual
per-database Render dashboard step, not yet enabled — `render.yaml`
documents where to find it); production Postgres remains commented-out
scaffolding, not provisioned, per the user's explicit choice to wait for a
real launch; and one known-but-unaddressed Postgres gotcha in the baseline
migration — `downgrade()` drops tables but not the Postgres `ENUM` types
those columns use, so a `downgrade base` → `upgrade head` cycle would hit
"type already exists". This never happens on the automatic `stamp`-or-
`upgrade` path `run_migrations()` actually uses, only on a deliberate
manual downgrade — worth fixing properly if that's ever needed, not urgent
otherwise.

**Epic 1.b (CI/CD Pipeline) — 1.b.i and 1.b.iv done, 1.b.iii in progress,
1.b.ii genuinely blocked:**

- **1.b.i "CI workflow for lint/type-check/test" — done.** This was a much
  bigger lift than "add a workflow file" once actually done properly: the
  codebase had never been linted or type-checked before, so getting a
  meaningful, genuinely-green CI baseline meant fixing real findings, not
  just wiring up tools. Full detail worth knowing if this needs revisiting:
  - `.github/workflows/ci.yml` — 3 parallel jobs (lint/typecheck/test), no
    external account needed (unlike everything in Epic 1.a) since GitHub
    Actions just runs on push/PR once the workflow file exists.
  - `pyproject.toml` — `[tool.ruff]` deliberately selects only `["E", "F"]`
    (pyflakes + pycodestyle), not ruff's broader defaults: a first pass with
    everything ruff can check surfaced 273 findings, but ~230 of those were
    either FastAPI's idiomatic `Depends(...)` default-argument pattern being
    flagged by flake8-bugbear's B008 (a well-known false positive for
    FastAPI codebases), or pyupgrade/import-sorting style preferences
    unrelated to correctness. `line-length = 135` matches the codebase's
    actual longest line rather than forcing a reformat of ~260 lines of
    deliberately-verbose docstrings/comments. `alembic/versions/` is
    excluded — it's autogenerated and, once applied, shouldn't be hand-
    edited to satisfy a linter.
  - The **real** findings that got fixed, not suppressed: 11 unused
    imports; 6 SQLAlchemy cross-file relationship type hints (e.g.
    `Mapped["Project"]`) that were flagged `F821 undefined-name` — fixed
    with `TYPE_CHECKING`-guarded imports (the standard SQLAlchemy 2.0
    pattern, not a `noqa` suppression, and it helps mypy too); a genuine
    type-hint bug in `Device.app_version` (annotated `Mapped[str]` but the
    column is `nullable=True` — now `Mapped[Optional[str]]`); a mypy false
    positive in `main.py` caused by `import app.models` binding the bare
    name `app` in a file that also defines `app = FastAPI(...)` — fixed by
    switching to `from app import models`, a pure naming fix with zero
    behaviour change; a dict-literal type-inference gap in
    `CATEGORY_KEYWORDS` (one entry's empty lists made mypy infer the whole
    dict too loosely) — fixed with an explicit annotation.
  - The largest category (~50 findings across `applications.py`,
    `contracts.py`, `projects.py`, `policies.py`, `local_search.py`,
    `recommendations.py`): SQLAlchemy `.query().filter().first()` returns
    `Optional[Model]`, and a lot of endpoint code used the result
    unchecked. Investigated whether this was mypy failing to see an
    existing guard (it wasn't) or a genuine gap (it was) by reading
    `auth.py`'s registration flow — confirmed a `STUDENT`/`BUSINESS`-role
    `User` is always created atomically with its `StudentProfile`/
    `BusinessProfile` in the same transaction, and several other cases are
    guaranteed by a `NOT NULL` FK (e.g. `Application.project_id`). Fixed
    every one with a documented `assert x is not None, "<why this can't
    actually be None>"` right after the query — narrows the type for mypy,
    documents the invariant in the code itself, and fails loudly if the
    invariant is ever actually violated (which would be a real bug, not a
    normal "not found" case, so a 500 from a failed assert is more honest
    than a misleading 404 would be). Did **not** touch the genuinely
    user-facing "this ID might not exist" cases — those already had proper
    `if x is None: raise HTTPException(404, ...)` guards.
  - Also fixed the **one pre-existing failing test**
    (`test_collaborative.py`) while making CI green — it was a test-fixture
    bug, not a scorer bug: `collaborative_score` requires
    `MIN_SIMILAR_STUDENTS_FOR_SIGNAL = 2` before returning a signal
    (documented, intentional), but the failing test only seeded one similar
    student. Fixed by seeding two, matching the pattern already used
    correctly in the sibling test right above it.
  - End state, actually verified: `ruff check .` → 0 errors, `mypy app/
    scripts/` → 0 errors across 65 files, `pytest` → 41/41 passing, app
    still boots. Added `ruff==0.16.5`/`mypy==2.3.1` to `requirements-dev.txt`
    pinned to what CI actually uses.
- **1.b.iv "document and script a one-command rollback" — done, as
  documentation, not a custom script.** README gained a "Rollback
  procedure" section (app-level: Render's deploy history or `git revert` +
  push; schema-level: `alembic downgrade -1`, with the known Postgres ENUM
  gotcha noted). Didn't write a separate script because both paths are
  already single commands — there was nothing left to script.
- **1.b.iii "staging auto-deploy + gated production deploy" — in
  progress, not verified.** Render very likely already auto-deploys
  `caplink-api` on push to `main` by default (matches everything observed
  during the Epic 1.a.iv troubleshooting), but this wasn't actually checked
  in the dashboard this session, so it's marked in-progress rather than
  done. **Action for next session: confirm Auto-Deploy is On in
  `caplink-api`'s Settings tab.** "Gated production deploy" has nothing to
  gate yet — no production service exists.
- **1.b.ii "Docker image build on merge" — genuinely blocked, not
  deprioritised.** This needs a Dockerfile to build from, and
  containerizing the app is a *different* epic's item (1.d.i, Workstream 1
  Epic d), not started. Revisit once 1.d.i lands — building this before
  then would mean building against nothing.

**Epic 1.c (Observability) — 1.c.i done, 1.c.ii/1.c.iii in progress
(code/docs done, external accounts pending), 1.c.iv deliberately deferred:**

- **1.c.i "Structured JSON logging" — done, and worth reading closely if
  logging or migrations need touching again.** `app/core/observability.py`
  adds a JSON formatter + `configure_logging()`, called from `main.py`'s
  startup hook (after uvicorn's own logging setup, so it wins, not the
  reverse) and covering uvicorn's own request/error loggers too, not just
  the app's `logger.info(...)` calls. `RequestLoggingMiddleware` in
  `main.py` emits one structured line per request with real separate
  fields (`request_id`/`method`/`path`/`status_code`/`duration_ms`) and
  replaces uvicorn's own plain-text access log rather than duplicating it
  (that log is explicitly disabled, not just reformatted).

  **Found a real, non-obvious bug while actually verifying this worked**
  (via `TestClient`, not just code review — the first attempt looked fine
  by inspection and was actually silently broken): `alembic/env.py` calls
  `logging.config.fileConfig(alembic.ini)` as a side effect of loading,
  every single time `run_migrations()` runs — including the second,
  redundant call inside `scripts/seed_demo_data.py`. That call does two
  destructive things at once: it resets the ROOT logger to `alembic.ini`'s
  own plain-text config (`[logger_root] level=WARN`), and — because
  `fileConfig`'s `disable_existing_loggers` defaults to `True` — it
  silently **disables** every other already-created logger not explicitly
  listed in the ini, including every `caplink.*` logger and uvicorn's. A
  disabled logger drops every message with zero error, so the first
  attempt just... didn't log anything, ever, with no exception anywhere to
  point at why. Fixed at the root, not patched around: `disable_existing_
  loggers=False` in `env.py`, plus `run_migrations()` now saves and
  restores the root logger's handlers/level around the alembic call so
  this can never leak out again regardless of who calls it or how many
  times. **Lesson for next time something like this gets added: verify
  observability changes by actually triggering the code path and reading
  the output, not just by checking the code compiles/imports cleanly** —
  this one would have shipped silently broken otherwise.
- **1.c.ii "Sentry error tracking" — DONE, verified end-to-end, not just
  wired up.** `sentry-sdk[fastapi]` in `requirements.txt` (safe to always
  install, unlike `firebase-admin` — no wheel-build risk); `SENTRY_DSN`
  setting (empty = no-op); `configure_error_tracking()` called at startup;
  exceptions captured **explicitly** via `sentry_sdk.capture_exception()`
  inside `main.py`'s existing global exception handler, rather than relying
  only on Sentry's own auto-instrumentation — that handler already catches
  everything and returns a clean JSON response, so there's no "unhandled
  exception" left for generic auto-instrumentation to necessarily notice.
  `SENTRY_DSN` was also missing from `render.yaml` entirely at first (a gap
  from when this was originally coded — the Settings field existed but
  Render had no slot for a human to actually set it) — added as `sync:
  false`, same as the other secrets. The user created a real Sentry
  account/project, set the real DSN in Render's dashboard, and a temporary
  `/debug-sentry` route (deliberately raising, exercising the real handler)
  was added, deployed, triggered directly against the live staging URL
  (`curl` → clean `500 {"detail":"Internal server error"}`, confirming
  staging's error-hiding behavior too), confirmed showing up in Sentry's
  Issues page tagged `environment=staging`, then removed. Real account,
  real DSN, real captured error — genuinely closed out.
- **1.c.iii "Uptime monitoring" — documented only (~20%), zero
  configuration exists.** This step is ~100% external — there was
  genuinely nothing to add to the repo beyond documentation. README's
  Observability section recommends a free monitor (e.g. UptimeRobot)
  polling `/health` every 5 minutes, and flags an important caveat:
  `/health` only confirms the process is up, not that the database is
  reachable — a DB-down scenario currently only surfaces as request-level
  500s in the logs/Sentry, not as a monitoring alert on its own.
- **1.c.iv "Latency dashboards" — not started, deliberately.** Matches its
  own P2/Medium-effort rating exactly — needs a real APM/dashboarding tool
  that doesn't exist yet. The structured per-request fields from `1.c.i`
  (method/path/status_code/duration_ms) are exactly what a future
  dashboard would query, so doing `1.c.i` properly now pays off later
  regardless of when this gets picked up.

**Epic 1.d (Hosting & Scaling) — 1.d.i done, 1.d.iv in progress
(documented, unverified), 1.d.ii deliberately deferred, 1.d.iii genuinely
blocked:**

- **1.d.i "Containerize the application" — done, but flagged as
  unverified.** `Dockerfile` (single-stage `python:3.13-slim`, non-root
  user, respects `$PORT` the same way `render.yaml`'s `startCommand`
  already does) and `docker-compose.yml` (runs that same Dockerfile
  against a **real local Postgres container**, not SQLite — specifically
  to catch Postgres-only issues the SQLite dev path can't, e.g. the ENUM-
  downgrade gotcha noted in `app/db/migrations.py`) plus a `.dockerignore`
  keeping secrets/local DB/dev cruft out of the image. **No Docker was
  available in this environment**, so none of this has actually been
  built or run — written carefully against dependencies already confirmed
  to resolve to prebuilt wheels on Linux (via Render's own build logs
  captured earlier in this file), but genuinely unverified until someone
  actually runs `docker build`/`docker-compose up`. **This also unblocks
  `1.b.ii`** (Docker image build on merge to main), which was blocked on
  this exact Dockerfile not existing — worth picking up together if `1.b`
  gets revisited.
- **1.d.ii "Managed container host with autoscaling" — deferred, the
  user's explicit choice.** Asked directly rather than assuming, since
  this has real cost implications: Render's free tier (what `caplink-api`
  runs on) has no autoscaling, only paid plans do, and this is a
  pre-revenue, pre-pilot product with no traffic problem to solve yet.
  Revisit once real usage actually justifies it.
- **1.d.iii "CDN for the frontend build" — genuinely blocked, not
  deprioritised.** This step assumes a compiled frontend build to put
  behind a CDN, which doesn't exist — `static/demo`/`static/app` are
  plain HTML/JS served directly by FastAPI's own `StaticFiles`, not a
  build output. The real frontend is Workstream 5 (not started). The
  existing static marketing pages (`docs/index.html`, `docs/prototype.html`)
  already get free CDN-like hosting via GitHub Pages per the README's
  existing "Hosting the static pages" section, so arguably the only part
  of this that currently *could* apply is already covered.
- **1.d.iv "Automated backups with a tested restore" — in progress
  (~30%), documented but not actually run.** README gained a "Database
  backups" section: manual `pg_dump` backup, `pg_restore`-into-a-separate-
  database restore drill, with a row-count spot-check step — matching the
  user's explicit choice (asked alongside `1.d.ii`, same reasoning) to
  document rather than build a stopgap on the free tier. Real automated
  backups need a paid Postgres plan, deliberately deferred like `1.d.ii`.
  **The restore drill itself has not been run for real** — no Docker/
  Postgres available here to test it against. Whoever picks this up next:
  actually run it once, deliberately, before trusting it.

## Workstream 2 (Auth Hardening), Epic 2.a — all four steps done, 2026-09-05

This was a much bigger lift than the Small/Small/Small/Medium effort
ratings suggest once actually implemented properly with real verification,
not just wired up. All four ended up genuinely done, not partially:

- **2.a.i (password policy)**: `app/services/password_policy.py` — local
  complexity rules + a live HaveIBeenPwned Pwned Passwords check (free,
  keyless, k-anonymity: only 5 hex chars of a SHA-1 hash ever leave this
  process). Fails open on a network error — a breach check shouldn't turn
  a third-party outage into an outage of registration for the whole
  platform. Applied at registration and a new `POST /auth/change-password`.
  **Actually verified against the live HIBP API** (a known-breached
  password was genuinely rejected via a real network call), not just
  mocked — the mocked unit tests exist separately, for CI.
- **2.a.ii (lockout)**: `app/services/account_lockout.py` (per-account,
  progressive: doubling backoff past `ACCOUNT_LOCKOUT_THRESHOLD` failed
  attempts — 5, 10, 20, 40 minutes...) plus `app/core/rate_limit.py`
  (per-IP, via `slowapi`). Worth knowing: **`slowapi` has been in
  `requirements.txt` since the very first commit of this repo but was
  never actually wired up until now** — `app.state.limiter` +
  `@limiter.limit(...)` decorators on login/register/resend-verification/
  mfa-verify. Verified end-to-end: 5 wrong passwords locks the account
  (423), the *correct* password is then also rejected while locked, and
  hitting the rate limit actually returns 429.
- **2.a.iii (email verification)**: a real confirmation-link flow
  (`GET /auth/verify-email?token=...`, `app/services/email.py` — same
  stub-until-a-real-ESP-exists shape as `notifications.py`'s push
  abstraction), replacing plain domain-string matching. **Auto-verifies in
  `development` only** — deliberately, not an oversight: no ESP is wired
  up yet, and zero-friction local dev/demo has been a stated priority
  throughout this project's whole history (see the dadster-guide section
  above) — making `static/app`/`static/demo`'s registration forms
  unusable without digging a token out of a log line would violate that
  for no real security benefit locally. Staging/production enforce the
  real flow. **This required updating both reference apps' registration
  JS** (`static/app/js/main.js`, `static/demo/app.html`) to handle either
  response shape (tokens directly in dev, a "check your email" message
  otherwise) — they call these endpoints directly and would have silently
  broken on staging otherwise. Verified the *real* (non-dev) path
  end-to-end by flipping `settings.ENVIRONMENT` to `"staging"` in-process
  against a local SQLite DB (Settings' own validator would reject
  staging+sqlite as a real deploy, but this sidesteps that just to
  exercise the verification logic itself): register → login blocked (403)
  → grabbed the token straight from the DB (same as reading it from the
  logged email with no ESP wired up) → verified → login succeeds.
- **2.a.iv (TOTP MFA)**: `app/services/mfa.py`, RFC 6238 via `pyotp` — no
  external account needed at all, just whatever authenticator app the
  admin already has. `/mfa/setup` persists a *pending* secret immediately
  (`totp_enabled` stays false) — same pattern as GitHub/Google's own setup
  flows — confirmed via `/mfa/enable` with a real code, which is also when
  8 single-use bcrypt-hashed backup codes get issued. Login for an
  MFA-enabled admin returns `mfa_required` + a short-lived, single-purpose
  `mfa` token type instead of real tokens, exchanged at `/mfa/verify`.
  **Deliberately not retroactively enforced** on existing admin accounts
  that haven't opted in — there's no admin UI yet to walk someone through
  setup, so hard-blocking would just lock people out with no way back in;
  it's real and immediate the moment `totp_enabled` actually flips true,
  not "on but unenforced" indefinitely. Verified the full cycle: setup →
  enable → login-challenge → wrong code rejected → correct TOTP accepted →
  backup code accepted once → same backup code rejected on reuse →
  disable requiring a valid code.

**One real bug caught before it ever shipped**: the autogenerated
migration (`alembic/versions/c5563aee8f62`) had three new `NOT NULL`
columns (`failed_login_attempts`, `totp_enabled`, `mfa_backup_codes`) with
no `server_default` — autogenerate doesn't add these on its own. Applying
that as-is would have crashed against any database with existing rows,
i.e. the real staging Postgres, which has real seeded users. Caught by
testing the migration against a DB with a pre-existing row (not just a
fresh one) before it ever shipped, fixed by hand, then reverified both
ways. **Confirmed genuinely working against the real live staging
deploy** after pushing — `/health` returned a clean 200 consistently for
90+ seconds post-deploy, meaning the migration applied cleanly to the
real database with real existing rows.

Two bugs also turned up in my own new *test* fixtures while running the
suite (not app bugs): a stale hand-computed SHA-1 value in a mocked HIBP
test, and `User(...)` objects built directly without a session not
getting their SQLAlchemy column `default=` values applied (those apply at
flush/INSERT time, not at bare Python construction) — both fixed, noted
here mainly as a reminder that hand-written test fixtures need the same
scrutiny as the code they're testing.

## Workstream 2 (Auth Hardening), Epic 2.b — 3/4 steps done, 2026-09-06

Follows straight on from Epic 2.a above. `2.b.i`–`2.b.iii` are genuinely
done; `2.b.iv` is backend-only (frontend blocked, same pattern as `1.d.iii`).

- **2.b.i (SAML 2.0 SP endpoint)**: `app/services/saml.py` (settings
  building, request translation, attribute mapping, IdP metadata parsing,
  role inference) + `app/api/v1/endpoints/saml.py` (the three actual
  routes: `GET /auth/saml/{slug}/metadata`, `GET /auth/saml/{slug}/login`,
  `POST /auth/saml/{slug}/acs`), via `python3-saml` (OneLogin) — it
  transitively depends on `xmlsec` (C bindings), confirmed to have prebuilt
  wheels for macOS ARM64 and manylinux x86_64 on Python 3.13 before adding
  it. Config is per-university (`University.saml_enabled`/
  `saml_idp_entity_id`/`saml_idp_sso_url`/`saml_idp_x509_cert`/
  `saml_attribute_mapping`, migration `c98cf682936f`), not a global switch.
- **2.b.ii (attribute mapping)**: `map_attributes()` translates whatever
  the IdP actually sends into CAPLink's shape via `DEFAULT_ATTRIBUTE_MAPPING`
  — standard eduPerson OIDs (mail, displayName, eduPersonAffiliation) that
  most real institutional federations (e.g. the UK Access Management
  Federation) actually expose, since student band/degree title are **not**
  standard eduPerson claims and most IdPs will never send them. A
  university can override any individual key via `saml_attribute_mapping`
  if theirs does expose something extra (tested with custom `yearOfStudy`/
  `degreeTitle` claims). A JIT-provisioned student without those claims
  gets a clearly-marked placeholder degree title to fill in via their
  profile after first login, rather than pretending SSO can conjure data
  it structurally can't.
- **2.b.iii (email/password fallback preserved)**: `saml_enabled` defaults
  to `False`; `/auth/login` is completely untouched by this epic. A
  university that hasn't configured SSO gets a clean 404 on
  `/auth/saml/{slug}/login`, not a broken partial SSO experience.
- **2.b.iv (metadata-upload admin UI)**: only the backend half exists —
  `POST /universities/{id}/saml-idp-metadata` parses one IdP-exported
  metadata XML file (via `OneLogin_Saml2_IdPMetadataParser`) and extracts
  entity ID/SSO URL/certificate automatically, instead of a university's IT
  team hand-copying three fields (especially the certificate — genuinely
  easy to get wrong by hand). `PATCH /universities/{id}/saml-config` covers
  manual entry too. The actual upload *screen* doesn't exist because there
  is no real frontend yet (Workstream 5, not started) — same "genuinely
  blocked, not deprioritised" situation as `1.d.iii`'s CDN item.

**The safety design decision this epic centres on**: the ACS handler
(`saml.py`'s `saml_acs`) will JIT-provision a new `STUDENT` account
automatically on any validly-signed assertion, but will **never**
auto-provision a `UNIVERSITY_ADMIN` account, even when the IdP's
affiliation claim says `staff`/`faculty`/`employee` — that role is what
controls which businesses can reach a university's student body at all
(the safeguarding gate this entire platform exists around), so granting it
for the first time needs an explicit human decision, not an unverified IdP
claim reaching an untested code path. Once an admin account already
exists (created some other way), SSO logs into it fine — the restriction
is only on *creating* one. An existing user's role/university is also
never changed by an SSO login (`account_mismatch` rejection if either
doesn't line up), so SSO can't be used to escalate or reassign anyone.

**Verification — genuinely end-to-end, not unit-tests-only.** 9 unit
tests in `tests/test_saml.py` cover the pure-function pieces
(`normalize_x509_cert`, `parse_idp_metadata`, `map_attributes`,
`infer_role`). Beyond that, a real cryptographically signed SAML assertion
was hand-built and tested through the actual FastAPI endpoints via
`TestClient` — genuine XML-DSig signing via `xmlsec` directly
(`xmlsec.tree.add_ids` + `xmlsec.template`/`SignatureContext`) against a
self-signed test IdP certificate, not a mocked library call. Confirmed
working: the metadata endpoint; the SP-initiated login redirect; a new
student JIT-provisioned correctly (role, `is_email_verified=True`, correct
`StudentProfile.band`/`degree_title` from custom mapped attributes); the
same user logging in again via SSO without creating a second row; a
staff-affiliation assertion with no pre-existing account being rejected
(`admin_account_not_provisioned`) with zero account created; a tampered
assertion being rejected (`assertion_invalid`) with zero account created;
a non-SSO-enabled university's login route 404ing; and plain
`POST /auth/login` continuing to work completely unchanged.

**One genuine bug hit and fixed while building the test harness — worth
knowing if this needs debugging again**: `TestClient`'s literal `Host`
header is `testserver` unless `base_url=` is passed explicitly, but
`app/api/v1/endpoints/saml.py`'s `SAML_BASE_URL` constant (used for the SP
entity ID / Audience check) is fixed at import time from
`settings.PUBLIC_APP_URL`. In a real deployment these always agree (the
real `Host` header *is* the configured `PUBLIC_APP_URL`), but in a
`TestClient`-only run they can silently diverge: the Audience check uses
one value, the Destination/Recipient check uses the other, and mismatching
either produces a correct-looking-but-wrong `assertion_invalid`. Also,
`testserver` itself is a single-label domain (no dot), which
`python3-saml`'s own settings validator rejects outright
(`sp_acs_url_invalid`) regardless of the above. Fixed by using a real
dotted test domain (`http://caplink.test`) consistently for both
`PUBLIC_APP_URL` and `TestClient(app, base_url=...)` — not a code bug, a
test-harness-only artifact, but a non-obvious one if this needs
re-verifying later.

**One genuine migration bug, same class as Epic 2.a's**: autogenerate
again produced a `NOT NULL` column (`saml_enabled`) with no
`server_default` — would have crashed applying against staging's already-
seeded university row. Fixed by hand (`server_default=sa.false()`) before
it ever shipped, verified against fresh + pre-existing-row DBs and a
downgrade/upgrade round-trip, same as every migration in this project so
far.

Full test suite reran clean after this epic: `ruff` 0 errors, `mypy` 0
errors (73 files), `pytest` 74/74 passing (65 pre-existing + 9 new).

## Workstream 2 (Auth Hardening), Epics 2.c and 2.d — 6/8 steps done, 2 external-only, 2026-09-06

Follows straight on from Epic 2.b above, completing the rest of Workstream 2.
`2.c.i`, `2.c.ii`, `2.c.iv`, `2.d.iii`, `2.d.iv` are genuinely done;
`2.c.iii` is real working backend code with only an external site key +
frontend widget missing; `2.d.i`/`2.d.ii` are documentation/checklists only
— both are literally about the account owner's own GitHub/Render account
settings, which this workspace has no login access to.

**2.c.i (rate limiting on messaging) — done.** `app/api/v1/endpoints/messages.py`'s
`create_thread` (30/minute) and `send_message` (60/minute) now carry
`@limiter.limit(...)`, same `slowapi` `Limiter` as 2.a.ii's auth endpoints.
Verified via TestClient: repeated calls past the limit return a real 429.

**2.c.ii (input sanitization / oversized-payload audit) — done, and the
source of this session's one genuinely nasty bug, same flavour as 1.c.i's
Alembic/logging gotcha:**

- Every free-text field across every schema in `app/schemas/*.py` now
  carries an explicit `max_length` (and every list field a max item count)
  — none of that existed before, so a client could previously send an
  arbitrarily large string or list and have it accepted and stored as-is.
- **The bug**: the natural way to write a global request-body-size cap is
  `BaseHTTPMiddleware` reading `request.stream()` in `dispatch()`. The first
  attempt did exactly that (`app/core/body_limit.py`) and looked completely
  correct — until actually exercising it via `TestClient` showed every
  downstream request arriving with an **empty body**, not the real one.
  Root cause, straight from Starlette's own source: `BaseHTTPMiddleware`
  wraps the request in a `_CachedRequest` whose docstring says outright —
  call `Request.body()` in `dispatch()` and the body gets cached and
  replayed to downstream apps; call `Request.stream()` instead (the natural
  choice for inspecting size without buffering) and downstream apps get an
  empty body so they "don't hang forever." Fixed by rewriting
  `MaxBodySizeMiddleware` as a **raw ASGI middleware** (wraps `receive`
  directly at the ASGI level, no `Request`/`_CachedRequest` involved at
  all) — checks `Content-Length` first, then raises a sentinel exception
  from inside `receive()` if the streamed total exceeds the cap, caught
  by the middleware itself to reply 413 (safe because nothing downstream
  has sent a response yet at that point — an ASGI app must never call
  `send` twice, so this only works because the exception fires before any
  `http.response.start`). Full account in the module's own docstring.
- Grepped the whole repo for raw SQL (`.execute()`/`text()`) — none exists;
  every query goes through the SQLAlchemy ORM, so SQL injection was never a
  live risk here.
- **One real stored-XSS vulnerability found and fixed** in the actively-used
  reference UI: `static/app/js/shared/contracts.js` rendered a contract's
  project title, counterpart name, and milestone descriptions via
  `innerHTML` **without** `dom.js`'s `esc()` helper — every other view in
  `/app` (`student.js`, `business.js`, `messaging.js`, `university-admin.js`)
  already uses it consistently; this one file was just missed. Concretely
  exploitable: a business could set their contact name or a milestone
  description to `<img src=x onerror=...>` and it would execute for
  whoever next viewed that contract card. **Verified against the real
  running app, not just by reading the diff**: started the dev server,
  logged in via the real API as the seeded business account, actually
  PATCHed a live business profile's `company_name` and posted a live
  project/contract with genuine `<script>`/`<img onerror>` payloads, then
  confirmed `esc()`'s exact escaping logic (reproduced faithfully, character
  for character) neutralizes those exact strings. A real Chrome click-through
  wasn't possible in this environment (browser extension not connected this
  session) — noted here rather than silently claimed.
- `static/demo/app.html` (the older, lighter-weight demo — see "The full
  app" section above) has the same class of gap in several places and was
  **deliberately left unfixed**: it has no `esc()` helper at all, and it's
  Workstream 5 (real frontend) territory to fix properly, not a quick
  patch — same "genuinely blocked, not deprioritised" reasoning as
  `1.d.iii`/`2.b.iv`. Documented in README, not silently dropped.

**2.c.iii (CAPTCHA bot protection) — in progress (~70%), real code verified
live, widget missing.** `app/services/captcha.py` verifies a new
`captcha_token` field (added to `StudentRegister`/`BusinessRegister`)
against hCaptcha's `siteverify` API — same "real code, external account is
the manual step" shape as Sentry (1.c.ii). No `HCAPTCHA_SECRET_KEY`
configured (the default everywhere) means every registration passes
regardless of token, so dev/demo is completely unaffected; fails open on a
network error, same reasoning as the HIBP breach check. **Verified genuinely
live, not mocked**: hCaptcha publishes a permanent, no-account-needed
integration-testing key pair specifically for this
(`https://docs.hcaptcha.com/#integration-testing-test-key-set` — secret
`0x0000000000000000000000000000000000000000`, always-passes response token
`10000000-aaaa-bbbb-cccc-000000000001`) — confirmed via a real network call
in `tests/test_captcha.py` and again via a `TestClient` session hitting the
actual registration endpoints (bad token → 400, real test token → 201).
**What's missing**: the actual hCaptcha widget on `/app`'s and `/demo`'s
registration forms, which needs a real site key (created alongside the
secret key, same free account) — genuinely blocked on Workstream 5, same
pattern as `2.b.iv`'s upload screen.

**2.c.iv (audit logging for admin/moderation actions) — done.**
`app/models/audit_log.py` (`AuditLog`, write-once — no PATCH/DELETE route
exists) + `app/services/audit_log.py::record_audit_event`, migration
`c2c089143636`. Records: a university admin's safeguarding-gate decision on
a business agreement (`policies.py::decide_agreement` — the plan's own
explicit example), a platform admin onboarding a new university
(`universities.py::onboard_university`), and a university admin's SAML
config changes (`update_saml_config`/`upload_saml_idp_metadata`).
**Deliberately narrower than the plan wording's illustrative examples**:
"rating overrides" and "account suspensions" aren't real features anywhere
in this codebase, so nothing was invented just to have something to log —
see the service module's own docstring for the reasoning. Readable via a
new `GET /audit-log` (platform-admin only). Verified end-to-end via
`TestClient`: a real agreement decision writes a row with the correct
actor/action/target_id/details, a platform admin reads it back correctly,
a university admin is correctly 403'd from the audit log itself. Migration
verified fresh + downgrade/upgrade round-trip — no `NOT NULL`-without-
`server_default` gotcha this time (unlike 2.a's and 2.b's migrations),
since this is a brand-new table, not new columns on an existing one with
real rows.

**2.d.i (MFA on internal infrastructure accounts) — in progress (~10%,
checklist only).** Purely a real-world account setting (GitHub, Render,
hCaptcha/Sentry) — this workspace has no login access to any of those
accounts to check or enable it, same limitation class as `1.c.iii`'s uptime
monitoring. README's new "Cyber Essentials technical controls" section
spells out the checklist and explicitly distinguishes it from CAPLink's own
admin-role TOTP MFA (2.a.iv, which protects app accounts, not the humans'
accounts on third-party services). Needs the account owner directly.

**2.d.ii (restrict database/admin network access) — in progress (~10%,
documentation/scoping only).** Worth reading the scoping note in README
closely: "admin-panel access" doesn't map onto anything in CAPLink at all —
there's no separate admin panel, university/platform admins use the same
`/app` reference UI as everyone else, gated by role (JWT+RBAC) not network
location, since university careers teams need to reach it from wherever
they work — so nothing was force-fitted onto that half of the step.
"Database access" does apply for real (Render Postgres's Internal vs.
External connection URLs); README documents the actual dashboard action
(check for an IP Allow List, restrict/retire the external URL) but it
needs the account owner's actual Render dashboard, which this workspace
doesn't have.

**2.d.iii (automated dependency vulnerability scanning) — done.**
`.github/dependabot.yml` — weekly version-update PRs for `pip`
(`requirements*.txt`) and `github-actions`. GitHub's own Dependabot, not
Snyk — no extra external account needed for a repo already on GitHub;
security *alerts* (distinct from these update PRs) are already on by
default for a public repo under Settings → Code security.

**2.d.iv (patch-management cadence) — done, as documentation**, same
"nothing left to actually automate" shape as `1.b.iv`. README documents a
fixed SLA (critical/high within 7 days, medium within 30 days, low at the
next routine pass) that 2.d.iii's Dependabot PRs get reviewed against, plus
a monthly Dockerfile base-image bump/rebuild cadence independent of
Dependabot (OS-level base-image CVEs aren't something a Python-ecosystem
scanner ever sees).

Full test suite reran clean after this epic: `ruff` 0 errors, `mypy` 0
errors (79 files), `pytest` 80/80 passing (74 pre-existing + 6 new:
`tests/test_captcha.py`, `tests/test_audit_log.py`).

## A real gap found 2026-09-07: verified work sat uncommitted for a full session

**Standing lesson, added to the top-of-file rule above**: at the start of this
session, `git status` showed the *entire* Epic 2.c/2.d session above —
genuinely implemented, tested, and TestClient-verified — had never actually
been committed or pushed. It only ever existed on this Mac's local disk,
one accident away from being lost, despite CLAUDE.md and the tracker
already describing it as "Done." The existing standing rule at the top of
this file (update the tracker/CLAUDE.md before ending a session) doesn't by
itself catch this — it's possible to update the *documentation* correctly
while never actually running `git commit`/`git push` on the code the
documentation describes. **Before ending any session that changed code, run
`git status` and confirm nothing meaningful is sitting uncommitted or
unpushed** — a green test suite on disk is not the same thing as a green
test suite the rest of the world (Render, GitHub Actions, a future session
on a different machine) can actually see.

This session's uncommitted backlog was found, confirmed safe (no secrets in
the diff — checked explicitly before staging), and pushed as three commits
(`32c7d87` the Epic 2.c/2.d work, `0741078` a missed contracts.js fix,
`a0c2a79` this session's Workstream 1 additions below) — see git log for
the real, final commit messages.

## Workstream 1 (Backend & Infrastructure), 1.b.ii and 1.b.iii closed out, 2026-09-07

Picking up Workstream 1 specifically (Phil's explicit choice — finish the
foundations before starting new surface area, having separately decided the
employer-discovery/outreach gap a stakeholder raised is not a blocker to
the existing roadmap — see the top-level `CLAUDE.md`'s Roadmap section for
that decision, it belongs there, not here).

- **1.b.ii ("Docker image build on merge") — done, and genuinely verified,
  not just wired up.** Was blocked since `1.d.i`'s `Dockerfile` didn't
  exist; it now does (previous session), but had never actually been run
  anywhere — no Docker in any environment this project has been worked on
  from. Added a `docker-build` job to `.github/workflows/ci.yml`
  (`docker build -t caplink:ci .`, no push to a registry — `render.yaml`
  deploys from source via Render's own Python buildpack, not this image, so
  there's nothing to publish to yet). Checked wheel availability for the
  two dependencies most likely to break a Linux container build before
  trusting this (`xmlsec`'s manylinux_2_28/manylinux2014 cp313 wheels,
  `psycopg2-binary`'s manylinux2014 cp313 wheel — both confirmed present on
  PyPI), then **pushed and actually watched the real CI run**: all four
  jobs (`lint`, `typecheck`, `test`, `docker-build`) came back
  `completed`/`success` — https://api.github.com/repos/philipmcareavey/CAPLink/actions/runs/34107613105.
  This is the first real confirmation the Dockerfile builds at all; running
  the container (and `docker-compose.yml` against real Postgres) is still
  unverified and shouldn't be assumed to work just because the build does.
- **1.b.iii ("staging auto-deploy + gated production deploy") — done for
  the applicable half, genuinely confirmed, not assumed.** `render.yaml`
  now declares `autoDeploy: true` explicitly for `caplink-api` instead of
  relying on Render's default — but the real confirmation came from
  watching what actually happened after the push above: **staging
  auto-deployed on its own**, no manual Render dashboard action taken by
  anyone. Confirmed two ways: `GET /health` stayed `200` throughout, and
  `GET /api/v1/audit-log` (a route that only exists in the code just
  pushed) returned `401` rather than `404` — a 401 means the route is
  registered and the new code is live; a 500 would have meant the new
  `audit_logs` migration broke against the real database with existing
  rows, which it didn't. "Gated production deploy," the other half of this
  step, remains not-applicable — there's still no production service to
  gate. Note for later: the `autoDeploy: true` line itself only actually
  takes effect on Render's side via a Blueprint **Sync**, not a plain
  push/deploy (same gotcha as `DATABASE_URL` elsewhere in `render.yaml`) —
  today's proof was of Render's *existing* behaviour, not of this specific
  line having taken effect yet.

Full test suite unaffected by either change (still 80/80, 0 lint/type
errors) — these were CI/infra-config additions, not application code.

## Workstream 3 (Payments & Payroll) — 10/15 done, 2/15 in progress, 2026-09-07

Phil's explicit direction: he agrees the employer-discovery/outreach gap a
stakeholder raised is real, but decided it's not a blocker to the existing
roadmap (see top-level `CLAUDE.md`'s Roadmap section — that decision lives
there, not here). Having just closed out `1.b.ii`/`1.b.iii`, he chose to
proceed with Workstream 3 next rather than the frontend (Workstream 5).
This is the single largest body of work completed in one session so far —
real financial infrastructure, not a documentation/config epic.

**The single most important design decision, worth understanding before
touching any of this again**: escrow (3.b.i/3.b.ii) and the platform-fee
split (3.a.iii) are the SAME mechanism, not two features. Every milestone
gets one PaymentIntent, `capture_method="manual"`, created at contract-
creation time — authorizing it (holding funds) IS the escrow. On the
self-employed rail it's also a **destination charge**
(`transfer_data.destination` = student's Connect account,
`application_fee_amount` = CAPLink's cut): capturing it later is the one
action that both takes the fee and pays the student, atomically. There is
deliberately no separate "now send the money" step. The PAYE rail
(3.c) skips `transfer_data`/`application_fee_amount` entirely — see
`app/services/stripe_payments.py`'s module docstring for the full
reasoning (a visa-restricted student must never look self-employed for
tax purposes via a personal Connect transfer).

**A genuine regression caught and fixed mid-session, worth knowing about
if this ever needs debugging again**: the first working version of this
correctly failed closed (`StripeNotConfigured`) whenever `STRIPE_SECRET_KEY`
was empty — technically correct for staging/production, but it would have
broken the existing zero-setup `/app`/`/demo` reference UIs outright, since
local dev has never had a real Stripe key and now every contract creation
requires one. Caught by actually running the existing demo flow via
`TestClient` after building the "real" path, not by reasoning about it in
the abstract. Fixed with `app/services/stripe_dev_mode.py`: every
`stripe_*.py` module now simulates (fake-but-consistent IDs, no real SDK
call) whenever `ENVIRONMENT=development` **and** the key is empty;
staging/production never simulate regardless. **A second, related bug**
surfaced while verifying this: `.env.example`'s `STRIPE_SECRET_KEY` held a
placeholder-looking value (`sk_test_xxx`) left over from before this
workstream existed and nothing ever read it — a fresh clone copying that
file verbatim would have a *non-empty* key, defeating the simulation check
and trying to call the real Stripe API with garbage credentials. Fixed in
`.env.example` (now genuinely empty, matching `HCAPTCHA_SECRET_KEY`'s
existing pattern) **and** in this Mac's own real `.env`, which had the
exact same stale value sitting in it.

**Status against the plan's 15 steps**:

- **3.a (Stripe Connect Core) — all 4 done.** `3.a.i`: student gets a real
  Connect Express account (`app/services/stripe_connect.py`); a business
  becomes an ordinary Stripe Customer with a saved default payment method
  (`app/services/stripe_customers.py`), **not** a Connect account — only
  payout recipients need one, and a business only ever pays. `3.a.ii`/
  `3.a.iii`/`3.a.iv` — real PaymentIntents, the fee split, and an
  idempotent webhook (`processed_webhook_events` table, verified via a
  hand-constructed real HMAC signature through `TestClient` — correct
  signature accepted, tampered signature 400s, redelivery of the same
  event id correctly no-ops) are all described together above since
  they're one mechanism.
- **3.b (Escrow & Milestone Flow) — all 4 done.** `3.b.i`/`3.b.ii` are the
  authorize/capture mechanism above. `3.b.iii` (refund/dispute) has two
  distinct endpoints, not one: `POST .../reject` (business rejects a
  submitted-but-unpaid milestone — cancels the authorization outright, no
  money ever moved) and `POST .../refund` (reverses a milestone already
  captured/paid — Stripe auto-reverses the associated Connect transfer
  too). `charge.dispute.created` webhook events also mark a milestone
  `DISPUTED`. `3.b.iv` — `scripts/reconcile_payments.py`, read-only,
  compares every Milestone against Stripe's live PaymentIntent record and
  logs drift; not wired into a scheduler (Render Cron Jobs is the natural
  home, a dashboard step this workspace can't perform).
- **3.c (Student Payroll Rail) — 2/4 done, 2/4 in progress.** `3.c.ii`
  (payment-rail field on Contract) and `3.c.iii` (hard PAYE-routing rule)
  are done — `app/services/payroll.py::determine_payment_rail` reuses the
  existing `visa_weekly_hour_cap is not None` signal rather than adding a
  second, potentially-inconsistent flag; verified both as a unit test and
  end-to-end (a visa-restricted student's contract lands on the PAYE rail
  and never even needs a Connect account). `3.c.i`/`3.c.iv` are
  genuinely, not just nominally, blocked on a real decision only Phil can
  make: **no umbrella/employer-of-record provider has been chosen** — this
  is a real commercial/legal relationship, not a technical one, so
  nothing here guesses at a specific vendor's API or file format. Built as
  a clean `PayrollProvider` interface + `LoggingPayrollProvider` stub
  (same shape as `email.py`/`notifications.py`) plus a generic CSV export
  (`GET /payments/payroll/export.csv`, platform-admin only) — real,
  working, tested code, just not pointed at any real provider yet.
- **3.d (Financial Reporting) — not started, deliberately.** All three
  steps are P2/post-launch in the plan itself; no time spent here this
  session, matching the plan's own prioritisation.

**A real, pre-existing security gap found and fixed while wiring this
up, unrelated to Stripe itself**: `accept-terms`, `submit`, and
`approve-and-pay` had no check that the caller was actually a party to the
contract — any authenticated business could previously act on *any*
contract, not just their own. Harmless while payment was a placeholder
string (`"pi_placeholder_replace_with_real_stripe_call"`); a real
vulnerability the moment approve-and-pay actually captures money. Fixed
via `_assert_is_contract_party`/`_assert_is_contract_business` in
`app/api/v1/endpoints/contracts.py`, applied to every mutating endpoint
on a contract or milestone, and verified via `TestClient`: a second,
unrelated business gets a real 403 trying to approve-and-pay, refund, or
reject someone else's milestone.

**Genuinely unverified against the real Stripe API** — Stripe has no
keyless or public-test-credential path (unlike hCaptcha/HaveIBeenPwned
elsewhere in this codebase), so nothing here has touched a real account.
What was actually verified: every Stripe SDK call written against
`stripe-python` 10.12.0's real installed, typed API; the simulated
dev-mode path end-to-end via `TestClient` with zero Stripe configuration
(the actual default everywhere); and the "real" code paths (destination-
charge/fee parameters, ownership checks, PAYE routing, webhook signature
verification/idempotency) via a second `TestClient` session with every
Stripe SDK function monkeypatched. New test files: `tests/test_stripe_payments.py`
(15 tests), `tests/test_payroll.py` (4 tests). Full suite: `ruff` 0 errors,
`mypy` 0 errors (87 files), `pytest` 96/96 passing (80 pre-existing + 16
new).

A new migration (`eede1a0f59da`) adds `processed_webhook_events`, Stripe/
payroll fields on `business_profiles`/`student_profiles`/`contracts`/
`milestones`, and three new `MilestoneStatus` values. Three separate bugs
were caught in this one migration before it was genuinely done — worth
reading closely if a migration ever needs a brand-new Postgres enum type
again:

1. The usual autogenerate NOT-NULL-without-`server_default` bug hit twice
   more (`contracts.payment_rail`, `student_profiles.stripe_connect_onboarded`)
   — fixed by hand, verified against a DB with pre-existing rows (a real
   seeded contract/milestone), same pattern as every previous migration in
   this project.
2. `milestonestatus` is a genuine native Postgres ENUM type, and adding
   new values to an *existing* enum type needs explicit `ALTER TYPE ...
   ADD VALUE` statements — autogenerate instead produced a generic
   `alter_column(type_=Enum(...))`, which on real Postgres would not
   actually add the new labels (it was comparing against SQLite's
   fallback VARCHAR representation, since this was generated against
   local SQLite). Fixed by hand with dialect-gated raw SQL
   (`if op.get_bind().dialect.name == "postgresql"`).
3. **A real, genuinely broken deploy, not just a reviewed-but-unverified
   risk**: pushing this migration to staging failed outright with
   `psycopg2.errors.UndefinedObject: type "paymentrail" does not exist`.
   Root cause: `op.add_column(...)` with a brand-new `sa.Enum(...)` type
   on an *existing* table does **not** create the underlying Postgres
   enum type first — unlike `op.create_table`, which creates any enum
   types its columns need as a side effect of the table itself being
   created. This is a completely different failure mode from #2 above
   (that one was about adding values to an enum that already existed;
   this one was about a brand-new enum type never being created at all),
   and the SQLite verification cycle couldn't have caught either — SQLite
   has no native enum type, so `add_column` there never needs one to
   exist first. Confirmed via Render's actual deploy logs (the only way
   to see this — no direct Postgres access from this workspace): Postgres
   uses transactional DDL, so the whole migration rolled back cleanly on
   both failed attempts, leaving staging safely on the previous revision
   rather than half-migrated — worth knowing that this specific failure
   mode is safe to hit, even if it shouldn't have shipped. Fixed with an
   explicit `sa.Enum(...).create(op.get_bind(), checkfirst=True)` before
   the `add_column` call (and a matching `.drop(..., checkfirst=True)` in
   `downgrade()`) — `checkfirst=True` makes both calls safe/idempotent
   no-ops on SQLite too. Re-verified the full SQLite cycle after the fix
   (fresh DB, pre-existing-row DB, downgrade→upgrade round-trip) — all
   clean — then pushed again and this time confirmed via the live
   deploy log that `alembic upgrade` actually completed successfully
   against real staging Postgres.

**The general lesson, worth remembering for any future migration that
introduces a brand-new Postgres enum type**: the SQLite dev-verification
cycle this project relies on (fresh/pre-existing-row/downgrade-upgrade)
is necessary but not sufficient — it cannot catch enum-type-specific
bugs at all, since SQLite has no equivalent concept. A migration touching
enum types for the first time needs either a real Postgres instance to
test against beforehand, or — as happened here — has to be caught for
real on staging and fixed in a fast follow-up. Docker's `docker-compose.yml`
(1.d.i) would give a real local Postgres to test against instead of
relying on a staging deploy to find this, if it's ever actually run — see
this file's earlier note that it's still unverified.

## Workstream 7 (Data Protection & Privacy Engineering) — 8/9 done, 1/9 a real flagged gap, 2026-09-07

Picked as the next workstream after Workstream 3 substantially closed out
— the plan's own text names Workstreams 3 and 7 together as "the most
likely gating factors for the first university pilot," so this follows
the same sequencing logic Phil already endorsed by choosing Workstream 3
over the frontend earlier. Full user-facing detail (the actual retention
policy, the anonymization design rationale, the data-residency finding)
is in README's new "Data protection & privacy engineering" section —
this entry covers what that section doesn't: verification, and a couple
of decisions worth flagging for whoever touches this next.

**The one deliberate design decision worth understanding before touching
account deletion again**: `DELETE /privacy/account` anonymizes, it does
not `DELETE FROM users`. This was a real design choice, not a shortcut —
see `app/services/privacy.py`'s module docstring for the full reasoning
(a contract/rating/message the deleted user was party to still belongs,
legitimately, to the other party's own record). Concretely: email →
`deleted-user-{id}@deleted.caplink.invalid`, name → "Deleted User",
password → a random unusable hash, MFA/verification tokens cleared,
`is_active=False`, `deleted_at` set, a student's `portfolio_urls` cleared
(personal links), device rows hard-deleted (push tokens are a physical-
device identifier with no reason to survive). Contracts/milestones/
ratings/messages are left completely alone. Requires re-entering the
current password first — same reauth-for-sensitive-actions pattern as
MFA disable.

**`scripts/data_retention.py` (7.a.i) defaults to a dry run** — `run(execute=False)`
only reports counts, `--execute` actually applies. Three rules: unverified
accounts >30 days old hard-deleted (safe — pre-verification, nothing else
can reference them yet); accounts inactive >24 months anonymized via the
same function as self-service deletion; `RecommendationLog` rows >12
months old hard-deleted (flagged during the 7.a.ii PII audit as the one
table that grows unboundedly per user with no other natural limit).
Required a new `User.last_login_at` field, set only on an actual
successful login (`account_lockout.py::register_successful_login`), not
at registration — an abandoned pre-verification signup is judged by its
own separate, shorter rule instead.

**Consent capture (7.b.i)** made `StudentRegister.data_sharing_consent` a
required (not `Optional[bool] = False`) field — omitting it is a 422, not
a silent opt-in. Both reference UIs (`static/app/js/main.js`,
`static/demo/app.html`) got a real checkbox wired to a client-side guard
before the request even goes out, plus the server-side check as the real
enforcement. `saml.py`'s JIT provisioning deliberately leaves
`data_sharing_consent_at` unset rather than backfilling a timestamp —
an SSO-provisioned student has never actually seen the consent wording,
so recording one would be fabricating consent that was never given; noted
as a known gap needing a real post-login consent screen once Workstream 5
exists.

**7.b.ii (cookie banner) is marked Done, not Not Started or Not
Applicable** — the plan step is explicitly conditional ("required *if*
analytics/cookies are used"), and a direct grep confirmed neither exists
anywhere in this codebase (auth is bearer-token-in-header, not cookie-
based). The audit confirming the precondition doesn't hold **is** the
deliverable here — revisit the moment analytics or cookies are ever
actually added.

**7.d.i (encryption at rest) verified via Render's own documentation and
community answers, not assumed**: Render Postgres uses AES-256 at rest by
default (primaries, replicas, and backups), no configuration needed.
**7.d.ii (TLS+HSTS)**: TLS termination is entirely Render's job (confirmed
the same way); `app/core/security_headers.py::HSTSMiddleware` adds the one
thing Render doesn't do on its own — telling a returning browser to never
fall back to plain HTTP — in every environment except `development`
(unit-tested directly against a minimal Starlette app rather than booted
through the full config, since `staging`/`production` config both hard-
require a real Postgres `DATABASE_URL` that doesn't exist in this
environment).

**7.d.iii (UK/EU data residency) is the one genuine, unresolved gap —
flagged, not worked around.** Confirmed directly from `render.yaml`:
both `caplink-api` and `caplink-staging-db` are in Oregon, USA. Render
does offer Frankfurt, Germany (confirmed via Render's own regions
documentation) as the realistic EU alternative. Not changed here —
moving region means recreating the database (the same region-must-match
gotcha already documented in `render.yaml` from `1.a.iv`, this time
against a database that holds real staging data) and is a genuine
infrastructure decision for Phil to make deliberately when he's ready,
not something to change unprompted mid-session the way this session
handled Workstream 3's provider-choice gap.

**Migration `c9fc3db88d6f`** adds `student_profiles.data_sharing_consent_at`,
`users.last_login_at`, `users.deleted_at` — all nullable, no enum
involved, deliberately the simplest possible shape after `eede1a0f59da`'s
real Postgres enum-creation lesson. Verified fresh/downgrade-upgrade on
SQLite; no pre-existing-row scenario needed since every new column is
nullable with no server_default required. Autogenerate again produced a
spurious `milestones.status` type-change line (same SQLite-only false
positive as `eede1a0f59da` — MilestoneStatus's actual members haven't
changed since then) — recognised immediately this time and removed
before it could cause any confusion, rather than needing a live failure
to catch it again.

Full test suite: `ruff` 0 errors, `mypy` 0 errors (91 files), `pytest`
105/105 passing (96 pre-existing + 9 new: `tests/test_privacy.py`,
`tests/test_data_retention.py`, `tests/test_security_headers.py`).
End-to-end verified via `TestClient`: registration correctly rejects
missing/false consent and records a real timestamp on success; the SAR
export endpoint returns real nested data across every table touched;
account deletion correctly requires the current password, then genuinely
anonymizes; the anonymized account can no longer log in at all.

## Workstream 5 (Frontend Web Application Build) — in progress, 2026-09-09

Picked next per Phil's explicit direction ("proceed with workstream 5")
after Workstreams 3 and 7 substantially closed out. This entry covers the
session's decisions and bugs; see README's new "Frontend web application"
section for the user-facing detail on what was actually built.

**The technology decision, made explicitly with Phil, not silently
resolved either way**: the plan's own wording asks for the design
system/components "as production React components." This environment has
never had Node.js/npm at any point in this project's history — there was
no way to install, compile, or verify a single line of React here, unlike
lower-risk unverified artifacts elsewhere in this project (e.g. the
Dockerfile, one standard file with well-understood syntax) where an
unverified-but-reasonable draft was an acceptable tradeoff. Presented this
tradeoff via `AskUserQuestion` rather than picking an extreme unprompted;
Phil chose "extend the existing vanilla-JS approach" — build all three
portals to real production quality (design tokens, a real component
library, full accessibility work) using the same no-build-step
architecture `static/app/` already uses, fully verifiable end-to-end
rather than a compile-unverified React tree.

**Two real, pre-existing production bugs found and fixed, both predating
this session** (from Epic 2.b/Workstream 3 respectively, never caught
because nothing had exercised these exact paths end-to-end before):

1. SSO login and Stripe Connect onboarding both redirected to
   `/app/app.html` — a file that has never existed anywhere in this
   repo's history (the real entry point is `/app/index.html`). Fixed via
   `sed` across `app/services/stripe_connect.py` (3 occurrences) and
   `app/api/v1/endpoints/saml.py` (2 occurrences).
2. Worse, independent of bug #1: `static/app/js/main.js` never actually
   implemented `consumeSsoHandoff()` — the function `saml.py`'s own
   docstring claimed existed and read the tokens back out of the redirect
   URL fragment. It didn't exist at all. **SSO login was completely
   non-functional end-to-end** the whole time Epic 2.b called itself
   "done" — the backend half was genuinely correct and well-tested (see
   Epic 2.b's own entry above), but nothing ever consumed its output on
   the frontend. Fixed by writing the function from scratch and wiring it
   to run before the first `render()` call on script load.

**What got built**:
- `static/app/css/tokens.css` (new) — 5.a.i. Pulled the colour palette out
  of `app.css`'s previously-unlabelled inline `:root` block, documented
  what each token is *for*, added spacing/radius/type/motion/elevation
  scales that didn't exist before (every value in `app.css` was ad-hoc
  pixels).
- `static/app/js/components.js` (new) — 5.a.ii. `renderMatchDial`,
  `renderProjectCard`, `renderStudentCard`, `openRatingModal` — vanilla-JS
  render functions substituting for the plan's named React components
  (see the technology decision above). `openRatingModal` uses a real
  `<dialog>` element specifically for the free focus-trapping/Escape/
  backdrop behaviour a hand-rolled overlay div would have to reimplement.
  `student.js`'s `renderProjectMatchCard` and `shared/contracts.js`'s
  inline rating form were refactored to actually call these instead of
  keeping duplicate ad-hoc markup — the point of a component library only
  holds if things actually import from it.
- **5.c.ii's match-explanation drill-down needed a genuinely new backend
  endpoint**, not just frontend wiring: the existing
  `GET /projects/{id}/match-explanation` in `projects.py` is
  student-only — it scores whoever's calling it, with no `student_id`
  parameter, so a business could never have called it for a specific
  shortlist candidate. Added
  `GET /projects/{id}/shortlist/{student_id}/explanation` in
  `applications.py`, reusing `matching.score_student_against_project()`
  and the same `access_control.filter_students_visible_to_business()`
  check `get_shortlist` already applies (verified via `TestClient`: a
  second, unrelated business gets a genuine 404, not just a
  code-review-time assumption that the check would work). Wired into
  `business.js` as a "View shortlist" / "Why this match?" flow.
- **5.d.ii checked against the actual mockup**, not assumed adequate:
  `../caplink-university-landing.html`'s "band control panel" section (a
  labelled-row-of-permit-pills visual) turned out to already match what
  `university-admin.js`'s agreement-approval UI does for its read-only
  summary (`.permit-pill`/`.lc-row`, same classes) — judged complete
  rather than reworked for cosmetic parity alone.
- **5.d.iii (employability reporting dashboard) — genuinely not started,
  not silently skipped.** P1/Large in the plan, zero backend aggregation
  exists to report on. Flagged rather than attempted half-built.
- **Accessibility (5.e)** — `static/app/accessibility.html` (new, linked
  from `/app`'s footer) is the real statement, not boilerplate: it names
  what was actually done, what's genuinely still a gap (no
  screen-reader read-through yet, tab strips lack the full ARIA tabs
  pattern despite being keyboard-operable), and how it was tested (manual
  expert review substituting for an unavailable axe-core toolchain — see
  5.e.i). Found and fixed one real keyboard-accessibility bug doing this:
  `shared/messaging.js`'s thread list was `<div class="item-card
  clickable">` elements with only a click handler — not Tab-reachable,
  not Enter/Space-activatable. Fixed by making them real `<button>`s (plus
  matching CSS in `app.css` to strip default button chrome so they still
  read as cards).

**Verification, and its real limit this session**: backend changes
verified via `TestClient` against a freshly seeded SQLite DB (this Mac's
existing dev `caplink.db` predates several recent migrations and isn't
safe to run ad-hoc scripts against without upgrading it first — used a
throwaway `DATABASE_URL` pointed at `/tmp` instead). Full suite: `ruff` 0
errors, `mypy` 0 errors (91 files), `pytest` 105/105 passing — no test
count change, since no new backend logic needed new unit tests beyond
what `TestClient` exercised directly for the one new endpoint. **The
claude-in-chrome browser extension was not connected this session**, so
none of the new/changed frontend code has been visually verified in a
real browser — a real gap relative to this project's usual standard for
frontend work (see "The full app" section above, which *was* verified via
real Chrome click-through). Substituted with: parsing every changed JS
file with `esprima` (installed temporarily, removed after) to catch
syntax errors; confirming every CSS class the new JS references actually
exists in `app.css`; and serving every changed/new static file through a
real running app instance to confirm none 404. **Do a real browser
click-through the next time the extension is available** — this
substitute is reasonable but not equivalent, and shouldn't be treated as
having fully closed out 5.e.i/5.e.ii/5.e.iii.

Not yet done this session, left for next time: a full screen-reader
pass, the ARIA-tabs pattern on the tab strips, and 5.d.iii. Tracker/README
updated to reflect exactly this partial state, not rounded up to "done."

### Visual repalette, same session, 2026-09-09

Straight after the above, Phil said the live result looked "clunky and
dated" and asked for something more modern, specifically citing Render's
own site/dashboard as a look he liked. Rather than guess at a redesign
blind, went and looked at render.com and dashboard.render.com directly
(both dark-by-default: near-black canvas, hairline borders instead of
shadows, one confident accent, monospace for anything technical), then
built the proposed direction as a standalone comparison artifact — applied
to CAPLink's real components (login panel, project card, dial, badges),
side by side with what was live — rather than describing hex codes in
prose. Iterated through several rounds on that artifact (dark → dark+light
toggle → light as the default → progressively more interactive demos: a
persona-switching hero, a live off-platform-contact-flagging chat demo, an
escrow milestone stepper, a working rating modal) before Phil approved it
and asked to implement it for real.

**What actually shipped, once approved — light as the default theme, not
dark**: `static/app/css/tokens.css`'s colour values changed (variable
*names* did not — `--brass`, `--moss`, etc. are kept as legacy labels since
renaming would touch every file that references them for zero visual
benefit; the file's own header comment now says so explicitly). Indigo-
violet (`#5457E5`) replaces brass/gold as the primary accent; a genuinely
new `--warn`/`--warn-soft` pair (amber) was added and wired into
`.badge.warn` — previously "pending"-type statuses reused the accent
colour itself, which stopped making sense once the accent became the
brand's primary colour rather than a muted decorative gold. Headings moved
from Fraunces (serif) to Sora (geometric sans), and technical/mono text
from IBM Plex Mono to JetBrains Mono — both loaded via the same Google
Fonts `@import` `app.css` already used, just a different family list.
Radius scale grew (3-6px hardcoded values → a `--radius-sm/md/lg` scale at
6/8/10px) and several hardcoded shadow/background values that had never
been tokenised (the header's translucent background, the modal backdrop,
the toast's box-shadow) were updated to match by hand since they weren't
reading from a token to begin with.

**One real, small usability fix came out of this, not just restyling**:
none of the three password fields on `/app` (login, student registration,
business registration) had any way to check what you'd typed before
submitting — added a real show/hide toggle (`.pw-toggle` in `app.css`,
`wirePasswordToggles()` in `main.js`), the one thing from the mockup that
was a genuine product gap rather than a visual preference.

**Verified in a real browser this time** — the claude-in-chrome extension,
disconnected for the rest of this session, got reconnected specifically to
do this (see the extension-troubleshooting exchange earlier in this
session if it drops again: check `chrome://extensions` is enabled, sign
into the extension with the same account as this session, then a full
Chrome quit-and-reopen, not just a new window). Clicked through the
reskinned login (including the new password toggle actually revealing/
hiding real typed text), the student feed's match dial, the business
shortlist + "why this match?" breakdown (5.c.ii, still working correctly
under the new palette), and the university admin's safeguarding permit
pills — all four screens confirmed rendering correctly against a fresh
local seed, not just reviewed as a diff. Full `ruff`/`mypy`/`pytest` suite
unaffected as expected (105/105, 0 lint/type errors) since this was a
CSS/JS-only change with no Python touched.

**Not touched, and still a real scope boundary worth knowing**: CAPLink's
*official* marketing site — `docs/index.html`, mirrored at the standalone
`../caplink-university-landing.html` outside git — was never touched by
any of this. Everything described below (persona hero, gate demo, escrow
stepper, chat-flagging demo, rating modal) landed on `static/demo/index.html`
instead — the lighter-weight, API-server-hosted "reference demo" landing
page, a different file with a different purpose (it exists to hand a
technical reviewer a working login, not to pitch a university's careers
office). It happened to have the same landing-page shape (hero, feature
grid, role cards) so the artifact's concepts transplanted onto it
directly; `docs/index.html` would need the same work done separately if
Phil wants it there too — not assumed, raise it explicitly first.

**`static/demo/` got the same repalette too, straight after, on request**
("update the demo with these features too"). Both `static/demo/app.html`
and `static/demo/index.html` are self-contained single files with their
own inline `<style>` — they don't import `tokens.css`, so the same colour/
radius/font values from the section above were inlined directly into each
file's own `:root` block, with a comment pointing back at `tokens.css` as
the source of truth. `index.html` uses different variable *names*
(`--navy`/`--teal` rather than `--ink`/`--brass`) since that's what the
file already called them — kept as-is, same "don't rename for zero visual
benefit" reasoning as everywhere else this session. The same password
show/hide toggle was added to `app.html`'s three password fields too
(inline `wirePasswordToggles()`, no separate `main.js` to put it in here).

**Then, the same day — Phil asked where the dynamic elements from the
artifact actually were** (they'd only ever existed in the standalone
artifact, never shipped), and asked for all four built into the real
`static/demo/index.html`: the persona-switching hero, the off-platform-
contact flagging demo, the escrow milestone tracker, and the stat
counters + rating modal. All four are now real, working client-side
JS/CSS on that page (one new `<script>` block at the bottom, ~250 lines —
this file had no JS at all before), each placed inside the existing
section that already discusses that concept rather than dumped in one
block: the persona tabs replace the static hero content, the gate-pill
demo sits at the end of `#safeguarding`, and the escrow/chat/rating demos
got a new `#see-it-work` section between `#how-it-works` and `#roles`.
**One real product decision made along the way, not just styling**: the
persona hero's live-card replaces what used to be the static
`assets/bridge-logo.png` image in that spot — which also incidentally
resolved the earlier-flagged gap where that raster logo's baked-in old
navy/teal colours no longer matched the new palette (the logo simply
isn't shown there anymore). The image file itself is untouched and still
exists; nothing else on the page references it now. Verified in a real
browser (both files) the same way as the main app: clicked through
`index.html` top to bottom and logged into `app.html` as the seeded
university admin to confirm the permit-pill agreement view still renders
correctly under the new palette. Full `ruff`/`mypy`/`pytest` suite
unaffected (105/105) — both files are static HTML/CSS/JS with zero Python
involvement.

The four new interactive elements were separately verified for real too,
not just reviewed as a diff: clicked every persona tab and confirmed the
headline/live-card actually swap (including the business "why this
match?" breakdown expanding and the university approve/reject buttons
updating the status pill with a working reset link); toggled a
safeguarding-gate pill between permitted/not-permitted; stepped the
escrow tracker through all three states to "paid" and back; typed a real
UK-format phone number and "let's move to WhatsApp" into the chat demo
and confirmed the flag banner appeared for both; and opened the rating
modal, clicked through the star picker, and closed it both via the × and
via submit. Checked the browser console after a full page load too — no
JS errors. `getComputedStyle` was used to double-check one thing that
looked wrong in a screenshot (the reason-chip text appeared almost
invisible) — it was genuinely fine (`rgb(68,72,214)` text on
`rgb(237,236,251)`, opacity 1), just JPEG screenshot compression washing
out a low-saturation colour pairing; worth remembering if a future
screenshot-based check flags something similar as broken.

## Workstream 8 (QA, Testing & Launch Readiness) — 8/10 done, 1/10 in progress, 2026-09-10

Phil asked what was currently blocked across all 8 workstreams and what could actually
be started; Workstream 8 came back as the strongest genuinely-unblocked candidate (no
external accounts needed for 8 of its 10 steps) and he said to proceed with it. Real
findings throughout, not busywork — this is the session that discovered the whole
pytest suite had never actually exercised the app through HTTP, and found and fixed a
genuine N+1 performance bug via real profiling, not guesswork.

**8.a.i/8.a.iii (test coverage) — the single most consequential finding this session.**
Before this, every one of the (then-)114 tests called a service function directly with a
bare `db_session` fixture — including every "verified via TestClient end-to-end" claim
scattered through this file's own history (SSO, Stripe payments, the contract-ownership
fix, CAPTCHA). Every one of those was a real, thorough, one-off manual script run once
during that session and thrown away — none of it was a permanent regression test.
`tests/conftest.py`'s new `client` fixture is a genuine `TestClient(app)` — the actual
app, actual routing, actual dependency injection — with `get_db` overridden to an
isolated per-test in-memory database. Deliberately does **not** use
`with TestClient(app) as c:` — that fires the ASGI lifespan protocol, which runs
`on_startup()`: real Alembic migrations plus (in development, the default) auto-seeding
demo data, both against `app.db.session`'s real global engine — i.e. this Mac's actual
`./caplink.db`, not the fixture's isolated one. Skipping the context manager skips
lifespan entirely; nothing this app needs at request time lives in `on_startup`, so
ordinary requests work identically either way.

Two subtler things the fixture has to handle, both real and easy to miss:
`settings.PASSWORD_BREACH_CHECK_ENABLED` gets monkeypatched off per-test (a real live
HaveIBeenPwned call already has its own dedicated test; every other test using this
fixture shouldn't depend on a real network call succeeding), and — the one that would
have caused real, confusing flakiness — `app.state.limiter.reset()` runs per-test, since
slowapi's `Limiter` is a module-level singleton shared across *every* test in the whole
pytest session (the `app` object is only ever imported once). Without the reset, a test
late in a run could get a spurious 429 from register/login calls earlier, unrelated tests
already made against the same in-memory rate-limit counters.

New test files: `test_golden_path_e2e.py` (the core product loop end-to-end — post,
apply, hire via milestone contract, pay both milestones through the simulated escrow
flow, mutual blind ratings; the safeguarding gate rejecting an unapproved business; a
permanent regression test for the real contract-ownership authorization bug found during
Workstream 3), `test_messaging_e2e.py` (thread creation, the off-platform-contact
flagging heuristic actually flagging a phone number and a suspicious phrase, a third
party correctly forbidden from a conversation, and a genuine 429 from the messaging rate
limit), `test_saml_endpoints_e2e.py` (SP metadata generation, the "SSO not enabled" 404 on
both the login and ACS routes). **Known, deliberately flagged gap, not silently
dropped**: the actual assertion-consumer path — a real IdP posting a signed SAML
response — still isn't a permanent test. Rebuilding that (a self-signed cert, a
spec-correct SAML Response, XML-DSig signing via `xmlsec`, and getting `SAML_BASE_URL`/
`TestClient`'s `base_url` onto a real dotted domain since python3-saml rejects
single-label hosts like `testserver`) is real, separate work — verified once, manually,
during Epic 2.b, but at the expense of the rest of Workstream 8 to rebuild properly here.
Given the size of "expand backend integration test coverage" as a Large-effort item,
8.a.i is marked in-progress (~40%), not done — real, substantial coverage of the most
critical flows now exists where none did before, but it doesn't yet reach every one of
the API's 67 endpoints. **8.a.ii (frontend component/unit tests) is genuinely blocked,
not attempted**: needs a JS test runner (Jest/Vitest), which needs a Node.js toolchain
this environment doesn't have — same blocker as the entire Mobile App workstream.

**8.b.i/8.b.ii (load testing & a real performance fix).** Seeded ~100 open projects
across 20 businesses (a throwaway script, not committed) and profiled
`GET /projects/feed` with `cProfile` — the endpoint that runs the full matching engine
across every visible project on every request, not just the page returned. Found a real
N+1: `collaborative_score` (the "students like you also succeeded here" factor) ran its
own "accepted applications in this category" query **once per candidate**, so ~100
candidates sharing ~8 categories issued the same handful of queries up to a dozen times
over, each also doing a nested per-accepted-application `StudentProfile` lookup inside
the old function. Fixed in `app/services/matching/collaborative.py`:
`fetch_accepted_pairs_by_category` runs one query per unique category a batch actually
needs (`Application` joined straight to `StudentProfile`, no per-row follow-up), and
`rank_projects_for_student`/`rank_students_for_project` compute it once up front, handing
each candidate its own slice via a new optional `collaborative_accepted_pairs` parameter
threading through `score_student_against_project` → `collaborative_score`. Single-score
callers (the business-side match-explanation drill-down, `test_collaborative.py`'s
existing tests) are completely unaffected — they simply don't pass a cache and get the
original one-query-per-call behaviour, just without the old inner N+1 either way. Measured
via `cProfile` before/after: ~100 DB round-trips → 1, wall time for the ranking pass
56ms → 34ms (~40% faster). **Honest caveat, not glossed over**: a concurrent-load
benchmark (50 requests at concurrency 10 via `httpx`+`ThreadPoolExecutor`) stayed noisy
and high (p95 ~500ms) even after the fix — SQLite's coarse-grained locking under
concurrent access is a dev-only artifact of this environment, not a production-Postgres
measurement. Re-running the same load test against real Postgres (e.g. via
`docker-compose.yml`, itself still unverified — no Docker here) once available is a real
follow-up, not done in this session.

**8.c.i (SAST/dependency scanning) — done, wired into CI, not just run once locally.**
`bandit` + `pip-audit` added as a new `sast` job in `.github/workflows/ci.yml`. One real
finding fixed: `hashlib.sha1(..., usedforsecurity=False)` in `password_policy.py` (the
SHA-1 there is HaveIBeenPwned's own k-anonymity protocol requirement, not a weak hash
protecting a secret — the flag was accurate that SHA-1 is weak, and also correctly
non-applicable to this specific, legitimate use). `~40` `B101` (`assert_used`) findings
are this project's own deliberately-documented `assert x is not None, "<why>"` invariant
guards from Epic 1.b — skipped project-wide via `[tool.bandit]` in `pyproject.toml`, same
reasoning as ruff's existing `B008` exclusion, not a blanket "assert is fine everywhere"
policy. Three `B105`/`B106` findings (JWT `token_type="access"`/`"refresh"`/`"mfa"`
string literals, and a comparison *against* — not a use of — the known dev placeholder
secret) are bandit false-positives on naive "contains the word password" string matching;
suppressed individually with inline `# nosec` comments naming exactly why, not swept away
project-wide the way B101 was (B101's false-positive pattern is genuinely project-wide;
these three are one-off). `pip-audit` found `pytest` 8.3.3 had a real, trivially-fixed
issue (bumped to 9.0.3, full suite re-verified clean on it) and one deliberate, ongoing,
documented exception: `ecdsa` (transitive, via `python-jose`) has an upstream-declared
wontfix timing-attack CVE against ECDSA signing — CAPLink's JWTs are always `HS256` (see
`Settings.ALGORITHM`), so the vulnerable code path is never actually exercised; CI's
`pip-audit` step ignores only that specific CVE ID, nothing else.

**8.c.ii/8.d.i/8.d.ii/8.d.iii (documentation) — all done, all grounded in this actual
codebase, not generic boilerplate.** README gained four new sections: a penetration-test
scoping brief (in/out of scope, target environment, seeded test accounts, and — notably —
this project's own already-known weak points named up front for a tester's attention,
rather than hoping they're rediscovered); operational runbooks for the incidents most
likely to actually happen (failed deploys, bad migrations, lockout/MFA recovery,
credential rotation, a stuck payment, an error-rate spike), each pointing at the specific
existing tooling that already helps (`scripts/reconcile_payments.py`, Sentry, structured
request logs) rather than inventing new process; admin/moderation playbooks for the real
decision surfaces that exist today (approving a partnership agreement, reviewing a
flagged message, reading the audit log, a milestone dispute, suspending a university's
license) — including one gap named rather than papered over (no dedicated "all flagged
messages" admin queue exists yet). **8.d.ii (API documentation) found a real, measurable
gap rather than assuming the auto-generated `/docs` were fine**: a scan of the live
OpenAPI spec found 26 of 67 endpoints had no real description at all, just FastAPI's
default title-cased-function-name summary. Added a short, accurate docstring to every one
of the 26 (register/login, creating a project, applying, creating a contract, submitting
a rating, sending a message, and others) — re-scanning after confirms 0/67 remain thin.

Full test suite after this workstream: `ruff` 0 errors, `mypy` 0 errors (114 files),
`pytest` 114/114 passing (105 pre-existing + 9 new: `test_golden_path_e2e.py` ×3,
`test_messaging_e2e.py` ×2, `test_saml_endpoints_e2e.py` ×4), `bandit` 0 findings,
`pip-audit` 0 unignored vulnerabilities.

## Clearing the remaining unblocked backlog: 2.b.iv, 2.c.iii, 5.d.iii — 2026-09-10

Straight after Workstream 8, Phil asked what was currently blocked across every
workstream and what could be proceeded with — a full triage found `2.b.iv` (SSO
metadata-upload screen) and `2.c.iii` (CAPTCHA widget) were no longer really
blocked at all (both had been waiting on Workstream 5's frontend existing, which
it now does) and `5.d.iii` (employability report) was the last unstarted P1 with
no external dependency. All three are now genuinely done, not partially — see the
top-level `CLAUDE.md`'s Roadmap section for the plain-English summary; this entry
covers the real implementation detail and the bugs found along the way.

**2.b.iv — SSO metadata-upload admin screen.** Before writing any frontend code,
checked whether a way to *read* current SSO config even existed — it didn't:
`app/api/v1/endpoints/universities.py` had `PATCH .../saml-config` (manual entry)
and `POST .../saml-idp-metadata` (XML upload), but both only ever returned
`SamlConfigOut` as the response to a *write*. An admin's screen needs to show
current state (SSO enabled? which entity ID is on file?) before letting them
overwrite it blind, so a new `GET /universities/{id}/saml-config` was added first
— same auth/ownership checks as the other two, no new schema needed since
`SamlConfigOut` already existed and already deliberately excludes the signing
certificate. The actual screen (`static/app/js/university-admin.js`, a new
"Single Sign-On" tab, `ADMIN_TABS`) offers both paths side by side: upload IdP
metadata XML (calls the existing POST, autofills nothing else) or fill in the
three fields by hand (calls the existing PATCH) — both re-fetch and re-render
the current-state banner on success. Verified for real in Chrome, not just via
`TestClient`: uploaded a genuine (if synthetic) SAML metadata document and
watched the entity ID/SSO URL get extracted and displayed; separately saved
manual-entry fields and confirmed the same round-trip.

**2.c.iii — hCaptcha widget, and a real script-loading race worth knowing about
if this pattern (a third-party widget on a form that doesn't exist at page load)
ever comes up again.** `app/core/config.py` gained `HCAPTCHA_SITE_KEY`, defaulting
to hCaptcha's own permanent, no-account, always-passes integration-testing site
key (`10000000-ffff-ffff-ffff-000000000001` — the sibling of the secret key
`tests/test_captcha.py` already used) — not secret, so safe to ship as a real
default rather than leaving the widget entirely absent until Phil creates a real
hCaptcha account. A new unauthenticated `GET /auth/captcha-site-key` lets the
frontend read whichever key is actually configured, so swapping in a real one
later needs zero frontend change. `static/app/js/main.js`'s registration forms
now mount a real hCaptcha widget (`hcaptcha.render()`) and send its response as
`captcha_token`.

The first version of this looked completely correct and did nothing: hCaptcha's
script was loaded with `render=explicit` (required, since the registration forms
this widget lives in don't exist in the DOM until a user switches tabs, well
after hCaptcha's own one-time automatic scan has already run) and
`onload=onHcaptchaLoaded`, with `onHcaptchaLoaded` defined inside `main.js`.
Nothing ever rendered. Root cause: `main.js` is loaded as an ES module
(`<script type="module">`), which browsers always defer — the async hCaptcha
script can finish loading and call `window.onHcaptchaLoaded()` *before* that
deferred module has run far enough to define it, and the resulting
`TypeError: onHcaptchaLoaded is not a function` happens silently inside
hCaptcha's own script with nothing surfaced to the page's own console in an
obvious way. Fixed by moving the callback into a tiny plain classic
`<script>` in `index.html` itself (guaranteed to run synchronously, in document
order, before the async hCaptcha script tag below it can possibly fire its
callback) — it just sets `window.__hcaptchaReady = true` and dispatches a
`hcaptcha-ready` event; `main.js` checks the flag first (covers hCaptcha
finishing first) and falls back to listening for the event (covers the module
finishing first).

**Verified genuinely end-to-end in a real Chrome browser**, not just via
`TestClient`: with a throwaway server started with `HCAPTCHA_SECRET_KEY` set to
hCaptcha's test secret (never committed to `.env`/`.env.example` — stays empty,
i.e. disabled, by default exactly like every other stubbed integration in this
project), solved the real rendered widget and completed a real registration.
**One real automation-tooling limitation worth noting for next time**: clicking
directly on the widget's checkbox via screen coordinates never worked, no matter
how carefully the coordinates were recomputed against the iframe's actual
`getBoundingClientRect()` — a cross-origin iframe checkbox turned out to only be
reliably activatable via real keyboard focus (Tab to it, Space to toggle), not
synthetic mouse clicks from this tooling. Once solved that way,
`hcaptcha.getResponse()` returned a real 36-character token and the full
registration (including hitting the real password-breach check, which correctly
rejected the shared demo password) went through end-to-end. `/demo`'s
registration forms were deliberately left untouched — same "Workstream 5 fixed
`/app`, not `/demo`" precedent as the earlier stored-XSS fix (see Epics 2.c/2.d's
entry above).

**5.d.iii — employability reporting dashboard.** `app/services/employability_report.py`
is pure aggregation over data that already existed — no new columns anywhere.
Worth knowing if this is ever extended: `Contract.status` is a real field, but a
grep confirms nothing in this codebase ever actually sets it to
`ContractStatus.COMPLETED` — so "completed" here is derived instead, as a
contract whose every milestone has actually reached `MilestoneStatus.PAID`, which
is a signal this project genuinely maintains. New `GET
/universities/{id}/employability-report` (university-admin only, own university
only) returns total/applied/hired/completed student counts, total earnings, an
average-rating figure (ratings *received by* a student, not given by one), and a
per-`StudentBand` breakdown of all of the above. `static/app/js/university-admin.js`
gained a new "Employability Report" tab (KPI tiles in a new `.stat-grid`/`.stat-tile`
pair of CSS classes, then a `.ledger-card` per band reusing the same row pattern
the Partnerships tab already used).

Verified via two new real HTTP-level tests
(`tests/test_employability_report.py`) that walk hire → both milestones paid →
mutual ratings through the real API and check the report's numbers at three
different points in that lifecycle (before any hire, after hiring but before
payment, and after full completion) — not just a single end-state assertion.
Also checked live in Chrome logged in as the seeded Manchester admin: the report
correctly reflected real data left over from this same session's earlier
browser-based testing (a genuine hired-and-paid contract from the CAPTCHA
verification work above), which is exactly the kind of live-computed-not-cached
behavior this endpoint is supposed to have.

**Tracker updated and independently re-verified, per this project's own standing
rule**: `2.b.iv`, `2.c.iii`, and `5.d.iii` moved to Done (100%) in
`CAPLink-Technical-Tracker.xlsx`'s `Tracker` sheet, and every one of the
Dashboard sheet's cached formula cells (overall counts, the per-workstream table,
the per-priority table) was independently recomputed from all 104 raw rows and
diffed — zero mismatches. A pre-edit backup sits at
`/tmp/tracker_work/CAPLink-Technical-Tracker.xlsx.backup-2026-09-10` on this Mac
if anything ever needs rolling back. New split: **65/104 done, 9/104 in
progress** (was 62/104 done, 11/104 in progress at the start of this session).

Full suite at the end of this work: `ruff` 0 errors, `mypy` 0 errors (93 source
files), `pytest` 117/117 passing (114 pre-existing + 3 new:
`test_captcha.py::test_captcha_site_key_endpoint_returns_configured_key`,
`test_employability_report.py` ×2).

## Dependency pinning — read this before touching requirements.txt

`requirements.txt` intentionally uses `>=` floors, not `==` exact pins. The
exact pins used to go stale (over a year old at one point) and broke fresh
installs on machines with newer Python, since pip couldn't find a matching
wheel and fell back to a source build that then failed. Floors let pip
resolve to whatever current release has a wheel for the installing machine.

Two non-obvious constraints exist for a reason — don't "clean these up"
without understanding why first:
- `bcrypt<4.1` — passlib 1.7.4 (unmaintained since ~2020) crashes against
  bcrypt>=4.1. This pin is safe forever wheel-wise: that version is built for
  the stable `abi3` ABI, so one wheel covers every Python 3.6+ release.
- `pydantic[email]` — the `EmailStr` fields in `app/schemas/user.py` /
  `university.py` need `email-validator`, which was never listed as its own
  dependency before (only worked locally by accident, via something already
  installed in an old venv).

`stripe`, `firebase-admin`, and `psycopg2-binary` are deliberately **not** in
requirements.txt — grep confirms none are actually imported anywhere in
`app/` yet (they're placeholders per the README's "what's stubbed" section).
They live in `requirements-integrations.txt` / `requirements-postgres.txt`
instead, installed only when those integrations get built out for real.

## If you're picking this up mid-troubleshooting

The account owner's dad (Windows machine, unrelated hardware/OS from this dev
Mac) hit a sequence of install/run failures, each fixed in turn:
1. `psycopg2-binary` — no wheel for his Python → moved out of requirements.txt
   (see "Dependency pinning" above).
2. A second unnamed package → traced to stale exact `==` pins across the
   board → loosened to `>=` floors.
3. **Root cause of the actual blocker, found from a screenshot of his error**:
   he had **Python 3.14** installed, not 3.13. Python 3.14 reimplemented
   `typing.Union` in C ([cpython#140348](https://github.com/python/cpython/issues/140348)),
   which breaks SQLAlchemy's declarative model scanning with
   `TypeError: descriptor '__getitem__' requires a 'typing.Union' object but
   received a 'tuple'` — a Python-version incompatibility, not a project bug,
   and not something a dependency change can fix. SQLAlchemy 2.0.51 has
   partial 3.14 support but not for this case, as of the last check (mid-2026).
   Fix: require **3.13** specifically — added `.python-version`, a README
   section ("Why Python 3.13, not 3.14"), explicit 3.13-only download
   instructions in the dadster guide's install step (python.org's homepage
   defaults to whatever is newest, which is exactly how he ended up on 3.14),
   and a troubleshooting entry recognizing this exact error text.

Verified (1) and (2) end-to-end in a clean throwaway venv on this Mac. (3) is
a well-documented, widely-hit regression, not something locally reproducible
on this Mac (which has 3.13) — the fix is high-confidence but **not yet
confirmed working on the dad's actual machine**. If this project comes up
again, check whether that confirmation came back before assuming it's fully
resolved.
