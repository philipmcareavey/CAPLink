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
2. Render reads `render.yaml` (included in the repo root) and provisions the API automatically.
3. Once deployed, update `CORS_ORIGINS` (in Render's environment variables) to include your
   GitHub Pages URL so the static prototype could eventually call the real API instead of
   its hardcoded demo data.

Note: Render's free tier has an ephemeral filesystem, so SQLite data resets on every
redeploy — fine for demoing, not for anything persistent. For that, add a Render Postgres
instance and point `DATABASE_URL` at it (see `.env.example`) — and add
`pip install -r requirements-postgres.txt` to the build command, since the Postgres driver
is kept out of the default `requirements.txt` (see below).

## Quickstart

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
ratings, messaging with off-platform-contact flagging, mobile device registration.

Integration points left as clearly-marked placeholders (each notes what to replace):
Stripe PaymentIntent creation/capture, Firebase push delivery, university-email domain
verification is currently a simple string match (swap for a real SSO/Shibboleth flow
for enterprise customers), and Alembic migrations aren't wired up (schema is created
via `create_all` for fast local iteration).
