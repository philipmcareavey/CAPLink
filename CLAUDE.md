# CLAUDE.md — orientation for whoever (human or agent) works on this repo next

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

## Technical Implementation Plan progress (Epics 1.a, 1.b done/near-done; 1.c in progress, 2026-08-30)

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
- **1.c.ii "Sentry error tracking" — code fully wired (~70%), no real
  account exists yet.** `sentry-sdk[fastapi]` added to `requirements.txt`
  (safe to always install, unlike `firebase-admin` — no wheel-build risk);
  `SENTRY_DSN` setting added (empty = no-op); `configure_error_tracking()`
  called at startup; exceptions captured **explicitly** via
  `sentry_sdk.capture_exception()` inside `main.py`'s existing global
  exception handler, rather than relying only on Sentry's own
  auto-instrumentation — that handler already catches everything and
  returns a clean JSON response, so there's no "unhandled exception" left
  for generic auto-instrumentation to necessarily notice. Verified both
  the empty-DSN no-op path and that init succeeds with a DSN-shaped
  string. **What's actually missing**: a real Sentry account/project —
  nothing here can create one. sentry.io has a free tier.
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
