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

Fully implemented: auth (including hardening — see below), multi-tenant licensing,
safeguarding access control, rules-based matching + recommendation logging, applications,
contracts/milestones with real Stripe payment authorization/capture/refund (see "Payments
& payroll" below), mutual blind ratings, messaging with off-platform-contact flagging,
mobile device registration, Alembic-managed schema migrations, structured JSON logging,
CI (lint/type-check/test), university SAML SSO (see "Auth hardening" below), GDPR
data-subject-rights tooling and an automated retention job (see "Data protection &
privacy engineering" below), a real design-token/component-library frontend covering
all three portals with WCAG 2.2 AA conformance (see "Frontend web application" below).

Integration points left as clearly-marked placeholders (each notes what to replace):
Firebase push delivery, verification emails are logged rather than actually sent (no ESP
wired up — see "Auth hardening" below), Sentry error tracking is wired up but inactive
without a real `SENTRY_DSN`, uptime monitoring isn't configured anywhere (see
"Observability" above), CAPTCHA verification is wired up but inactive without a real
`HCAPTCHA_SECRET_KEY` (no widget on the reference UIs' registration forms yet either —
see "API hardening & abuse prevention" below), and the payroll rail for visa-restricted
students has a real, enforced routing rule but no actual umbrella/EOR provider chosen or
integrated yet (see "Payments & payroll" below).

**One real, unresolved gap, not a placeholder**: staging is hosted in Oregon, USA, not
the UK/EU — see "Data protection & privacy engineering" below for why that matters and
what the alternative is.

## Payments & payroll

Technical Implementation Plan Workstream 3. Real Stripe Connect integration
— not a placeholder — covering student payouts, business charges, the
escrow-style milestone flow, and a hard payroll-routing rule for
visa-restricted students. `stripe>=10.12.0` is a hard runtime dependency
(`requirements.txt`, not `requirements-integrations.txt` — several
`app/services/stripe_*.py` modules import it at module load time).

- **Two separate Stripe identities per milestone.** A student gets a
  **Connect Express account** (`app/services/stripe_connect.py`) — the only
  way to actually receive a payout. A business becomes an ordinary
  **Customer with a saved default payment method**
  (`app/services/stripe_customers.py`), not a Connect account — it only
  ever pays, never receives. `POST /payments/connect/onboarding-link` +
  `GET /payments/connect/status` (student); `POST /payments/setup-intent` +
  `GET /payments/setup-status` (business).
- **Escrow via a single mechanism, not two bolted together**
  (`app/services/stripe_payments.py`). Every milestone gets its own
  PaymentIntent, created at contract-creation time with
  `capture_method="manual"` — the card is authorized (funds held) then,
  which *is* the escrow. On the self-employed rail it's also a destination
  charge (`transfer_data.destination` = the student's Connect account,
  `application_fee_amount` = CAPLink's cut): capturing it later — wired
  into the existing `POST /contracts/milestones/{id}/approve-and-pay` — is
  the single action that both takes the platform fee and pays the student,
  atomically. `POST .../reject` releases an unpaid authorization outright
  (`cancel`, not a refund); `POST .../refund` reverses money already
  captured (Stripe auto-reverses the associated Connect transfer too).
- **Idempotent webhook.** `POST /payments/webhook` verifies Stripe's
  signature against the *raw* request body, then de-duplicates via a
  `processed_webhook_events` table before acting — Stripe explicitly
  documents that the same event can be delivered more than once. Handles
  `payment_intent.succeeded`/`.payment_failed` and `charge.dispute.created`.
- **PAYE payroll routing (`app/services/payroll.py`) is a real, enforced
  business rule, not a stub**: any student with `visa_weekly_hour_cap` set
  (this project's existing "visa-restricted" signal) is automatically
  routed to the PAYE/umbrella rail on contract creation, never the
  self-employed rail, and never per-contract overridable. A PAYE-rail
  milestone deliberately skips `transfer_data`/`application_fee_amount`
  entirely — a visa-restricted student is never paid via a personal
  Connect transfer, since that would make them look self-employed for tax
  purposes, exactly what this rail exists to prevent. **What genuinely
  isn't built**: which umbrella/employer-of-record company actually
  receives that money. No provider has been chosen — this is a real
  commercial/legal relationship, not a technical decision this codebase
  can make on its own — so `PayrollProvider` is a clean, swappable
  interface (same "provider-agnostic stub" shape as `email.py`/
  `notifications.py`) with a logging placeholder implementation, plus a
  generic CSV export (`GET /payments/payroll/export.csv`, platform-admin
  only) rather than a guess at a specific provider's file format.
- **Nightly reconciliation** (`scripts/reconcile_payments.py`, step 3.b.iv)
  — compares every Milestone with a Stripe PaymentIntent against Stripe's
  own live record, read-only (flags drift, never auto-corrects). Not wired
  into a scheduler; Render's Cron Jobs (a separate dashboard-configured
  service type) is the natural home for it, same "code is real, the
  schedule is a manual step" shape as everything in the CI/CD notes.
- **Zero-friction local dev is preserved deliberately.** Stripe has no
  keyless or public-test-credential path (unlike hCaptcha/HaveIBeenPwned
  elsewhere in this codebase) — failing closed with no key configured
  would have broken the existing zero-setup `/app`/`/demo` reference UIs
  outright. `app/services/stripe_dev_mode.py` simulates every Stripe call
  with fake-but-consistent IDs whenever `ENVIRONMENT=development` **and**
  `STRIPE_SECRET_KEY` is empty — `staging`/`production` never simulate,
  regardless of key state, since a "successful" simulated payment there
  would be a real, expensive lie. `.env.example`'s `STRIPE_SECRET_KEY` used
  to hold a placeholder-looking value (`sk_test_xxx`) that nothing ever
  actually read — now that this workstream reads it for real, that
  placeholder was changed to genuinely empty, since a non-empty fake value
  would make dev try to call the real API with garbage credentials instead
  of simulating.
- **A real, pre-existing security gap found and fixed while wiring this
  up**: `accept-terms`, `submit`, and `approve-and-pay` had no check that
  the caller was actually a party to the contract in question — any
  authenticated business could previously approve-and-pay (or a student
  submit a milestone) on *any* contract. Harmless while payment was a
  placeholder string; a real vulnerability once approve-and-pay actually
  captures money. Fixed in `app/api/v1/endpoints/contracts.py` via
  `_assert_is_contract_party`/`_assert_is_contract_business`, applied to
  every mutating endpoint on a contract or milestone.
- **Genuinely unverified against the real Stripe API** — Stripe's complete
  absence of a keyless test path means nothing here has been exercised
  against a real account. What has been verified: every Stripe SDK call
  written against `stripe-python` 10.12.0's actual typed API; the
  simulated dev-mode path, end-to-end, via `TestClient` and this project's
  test suite (`tests/test_stripe_payments.py`, `tests/test_payroll.py`);
  and the real (mocked-SDK) code paths — correct destination-charge/fee
  parameters, the ownership-check fix, PAYE routing, webhook signature
  verification and idempotency — via a `TestClient` session with every
  Stripe SDK function monkeypatched. A real Stripe account and test-mode
  keys are needed before any of this is trustworthy in a real deployment.

## Auth hardening

- **Password policy** — complexity rules (8+ characters, upper/lower/digit) plus a check
  against [HaveIBeenPwned's Pwned Passwords API](https://haveibeenpwned.com/API/v3#PwnedPasswords)
  (free, keyless, k-anonymity — only 5 hex characters of a SHA-1 hash are ever sent, never
  the password itself). Fails open on a network error rather than blocking registration
  because a third party is down; toggle off entirely with `PASSWORD_BREACH_CHECK_ENABLED=false`.
  Applied at registration and `POST /auth/change-password`.
- **Account lockout** — progressive backoff per account (`ACCOUNT_LOCKOUT_THRESHOLD` wrong
  attempts locks it, doubling in length each attempt past that — 5, 10, 20, 40 minutes...),
  plus a per-IP rate limit (`slowapi`, 10/minute) on login/register/MFA endpoints as a
  separate, complementary layer.
- **Email verification** — a real confirmation-link flow (`app/services/email.py`, `GET
  /auth/verify-email?token=...`), replacing plain domain-string matching. **In development
  only**, registration auto-verifies and logs straight in (matches this project's
  zero-friction local-dev priority, and there's no ESP wired up yet to click a link from
  anyway) — staging and production enforce the real flow, so a new account there can't log
  in until the link is actually clicked. No real ESP is wired up, so that link currently
  only appears in the server's own logs.
- **MFA (TOTP)** — for `university_admin`/`platform_admin`. `POST /auth/mfa/setup` →
  `POST /auth/mfa/enable` (with a code from an authenticator app) → `totp_enabled` flips on,
  and login for that account then returns an `mfa_required` challenge instead of tokens
  directly, exchanged at `POST /auth/mfa/verify`. 8 single-use, bcrypt-hashed backup codes
  are issued on enable, for when the authenticator device is unavailable. Standard RFC 6238
  TOTP via `pyotp` — no external account needed, just whatever authenticator app the admin
  already has. Not retroactively enforced on existing admin accounts that haven't opted in
  (there's no admin UI yet to walk someone through setup) — real and immediate once
  `totp_enabled` is actually true, not merely "on but unenforced."
- **University SAML SSO** — a real SAML 2.0 SP flow (`python3-saml`) replacing the earlier
  plain domain-string match for *which institution* a student belongs to. A university
  admin sets `saml_enabled`/IdP entity ID/SSO URL/certificate on their `University` row
  (`PATCH /universities/{id}/saml-config`, or `POST /universities/{id}/saml-idp-metadata`
  to extract all three automatically from one exported IdP metadata XML file instead of
  hand-copying them) — this is additive per-tenant config, not a global switch, so a
  university that never enables it keeps using `/auth/login` exactly as before.
  `GET /auth/saml/{slug}/metadata` (SP metadata for the university's IT team),
  `GET /auth/saml/{slug}/login` (SP-initiated redirect to the IdP), and
  `POST /auth/saml/{slug}/acs` (assertion consumer service) implement the actual dance;
  a successful login hands the browser fresh CAPLink tokens via a URL **fragment**
  (`/app/app.html#access_token=...`), never a query string or log line.
  A signed assertion JIT-provisions a new **student** account automatically (marked
  `is_email_verified=True` — a valid signed assertion from the university's own IdP is
  stronger proof than the confirmation-link flow it stands in for here); an existing
  account just logs in as whatever role it already has. **Deliberately never
  auto-provisions a `university_admin` account**, even if the IdP's affiliation
  attribute says "staff" — that role controls which businesses can reach a university's
  students at all (the safeguarding gate this whole platform is built around), and
  granting it needs a human decision the first time, not an IdP claim; SSO logs into an
  admin account fine once one already exists. Most real institutional federations (e.g.
  the UK Access Management Federation) only expose standard eduPerson attributes
  (email, display name, affiliation) and not CAPLink-specific concepts like student band
  or degree title — `app/services/saml.py`'s `DEFAULT_ATTRIBUTE_MAPPING` reflects that,
  and a JIT-provisioned student gets a clearly-marked placeholder degree title to fill
  in via their profile after first login rather than pretending SSO can supply data most
  IdPs never send. A university can override any individual mapping via
  `saml_attribute_mapping` if their IdP does expose something extra.
  Verified end-to-end with a hand-built, cryptographically signed test SAML assertion
  (real XML-DSig signing via `xmlsec`, not a mocked library call): JIT provisioning,
  idempotent re-login of an existing account, staff-affiliation-with-no-existing-account
  correctly rejected without creating an account, a tampered assertion correctly
  rejected, and a non-SSO-enabled university's login route correctly 404ing.

## API hardening & abuse prevention

Technical Implementation Plan Epic 2.c.

- **Rate limiting** — `slowapi`, per-IP. Auth endpoints (login/register/
  resend-verification/MFA-verify) at 10/minute since 2.a.ii; messaging added
  in 2.c.i (`POST /messages/threads` 30/minute, `POST /messages` 60/minute)
  — the other realistic abuse surface once an account exists (spamming new
  conversations, or flooding a single one).
- **Oversized-payload protection** — two layers. `MaxBodySizeMiddleware`
  (`app/core/body_limit.py`) rejects any request body over
  `MAX_REQUEST_BODY_BYTES` (2MB by default — comfortably above the largest
  legitimate payload today, a SAML IdP metadata upload) before it reaches
  routing at all. Underneath that, every free-text Pydantic field across the
  API (names, titles, descriptions, message content, cover notes, milestone
  descriptions, SAML config fields, ...) carries an explicit `max_length`,
  and every list field a max item count — neither existed before this epic,
  so a client could previously send an arbitrarily large string or list and
  have it accepted and stored as-is.
- **Injection audit** — every query in this codebase goes through the
  SQLAlchemy ORM (confirmed via a full-repo grep for raw `.execute()`/`text()`
  calls — there are none), so classic SQL injection isn't a live risk here.
  The audit did find one genuine stored-XSS gap in the reference UI though:
  `static/app/js/shared/contracts.js` was rendering a contract's project
  title, counterpart name, and milestone descriptions via `innerHTML`
  *without* the `esc()` helper every other view in `/app` already uses
  consistently — fixed. `static/demo/app.html` (the older, lighter-weight
  demo — see "What's stubbed vs. production-ready" below) has the same gap
  in several places and was **not** fixed in this pass: it has no `esc()`
  helper at all, and giving it one properly is `static/demo`-specific
  frontend work, not a quick patch — known, tracked, not urgent given `/app`
  is the actively-used reference implementation (and the one Workstream 5
  actually built out — see "Frontend web application" below).
- **Bot protection (CAPTCHA)** — `app/services/captcha.py` verifies a
  `captcha_token` field on `POST /auth/register/student` and
  `.../register/business` against hCaptcha's `siteverify` API, same
  "real code, external account is the manual step" shape as Sentry
  (1.c.ii): with no `HCAPTCHA_SECRET_KEY` set (the default everywhere right
  now) it's a no-op and every registration passes, so local dev/demo is
  completely unaffected. Fails open on a network error, same reasoning as
  the HIBP breach check. **What's still missing**: the actual hCaptcha
  *widget* on `/app`'s and `/demo`'s registration forms — that needs a real
  site key (created alongside the secret key, same free hCaptcha account)
  and, now that Workstream 5's component library exists, is a small
  follow-up rather than a blocked one; just not done in this pass. To turn
  this on for real: sign up at hcaptcha.com, add the site key to the
  registration forms' JS, set `HCAPTCHA_SECRET_KEY` in Render's dashboard
  (already slotted into `render.yaml` as `sync: false`).
- **Audit logging for admin/moderation actions** — `app/models/audit_log.py`
  (`AuditLog`, write-once — no PATCH/DELETE route exists for it) records a
  university admin's safeguarding-gate decision on a business agreement
  (`PATCH /universities/{id}/business-agreements/{agreement_id}` — the
  plan's own explicit example, and the single most safeguarding-critical
  write in the platform), a platform admin onboarding a new university, and
  a university admin's SAML SSO configuration changes (security-sensitive:
  controls which IdP CAPLink trusts for that university). Readable via
  `GET /audit-log` (platform-admin only, newest first). **Narrower than the
  plan wording's illustrative examples on purpose**: "rating overrides" and
  "account suspensions" aren't actual features in this codebase at all, so
  nothing was invented to have something to log — see
  `app/services/audit_log.py`'s docstring.

## Cyber Essentials technical controls

Technical Implementation Plan Epic 2.d — UK Cyber Essentials is a
certification against real infrastructure/process, not application code, so
most of this epic is a checklist for the account owner to actually action
against GitHub/Render/hCaptcha accounts this workspace has no login access
to, rather than something to build. Two items *are* real repo changes:

- **Automated dependency vulnerability scanning (2.d.iii, done)** —
  `.github/dependabot.yml` adds weekly version-update PRs for both `pip`
  (`requirements*.txt`) and `github-actions` ecosystems. Security *alerts*
  (as opposed to these update PRs) are already on by default for a public
  GitHub repo like this one under Settings → Code security — nothing to add
  there.
- **Patch-management cadence (2.d.iv, done, as documentation)** — Dependabot
  PRs (above) get reviewed and merged against a fixed SLA: **critical/high
  severity within 7 days, medium within 30 days, low at the next routine
  dependency pass**. The `python:3.13-slim` base image in `Dockerfile`
  (1.d.i) should be bumped and rebuilt at least monthly regardless of
  whether Dependabot flags anything, since OS-level package CVEs inside a
  base image aren't something a Python-ecosystem scanner sees at all.
- **MFA on internal infrastructure accounts (2.d.i, not done — needs the
  account owner, not code)** — a Cyber Essentials baseline control, and one
  this workspace cannot verify or configure itself (no login access to
  these accounts). Checklist: enable 2FA/MFA on the GitHub account this
  repo lives under, on the Render account (`caplink-api`/
  `caplink-staging-db`), and on the hCaptcha/Sentry accounts once created
  above. CAPLink's own admin-role MFA (2.a.iv, `pyotp`/TOTP) is a *separate*
  thing — that protects `university_admin`/`platform_admin` accounts
  *inside* the app; this item is about the humans' accounts on the
  third-party services the app depends on.
- **Restrict database/admin network access (2.d.ii, not done — needs the
  account owner's Render dashboard, and a scoping note)**. "Admin-panel
  access" doesn't map onto anything in CAPLink structurally: there's no
  separate admin panel, university/platform admins use the same `/app`
  reference UI as everyone else, gated by role-based auth (JWT + RBAC) —
  not by network location, since university careers teams need to reach it
  from wherever they work. "Database access" does apply for real: Render
  Postgres exposes both an Internal Database URL (only reachable from
  services in the same Render region — what `caplink-api` actually uses)
  and an External Database URL (reachable from the public internet with
  just a password) for direct `psql`/admin access. Action for the account
  owner: check `caplink-staging-db`'s dashboard for an IP Allow List
  feature and restrict the external URL to known IPs (or stop using it
  entirely, relying only on the internal one) — not done here because it
  requires the actual Render dashboard.

## Data protection & privacy engineering

Technical Implementation Plan Workstream 7 — the technical controls a real
DPIA and university data-protection offices will expect to see evidenced,
not just documented. 8 of 9 steps done; the 9th is a real, flagged, unresolved
gap, not something quietly worked around.

- **Data retention (`scripts/data_retention.py`, step 7.a.i)** — the actual
  policy, not just the enforcement code: unverified accounts are deleted
  after 30 days (they hold essentially no activity — no contract is
  possible pre-verification, so nothing else has a legitimate interest in
  keeping them); accounts inactive for 24 months are anonymized (see
  below — not hard-deleted, for the same reason self-service deletion
  isn't); `RecommendationLog` rows (the one table in this schema that
  grows unboundedly per user with no natural cap otherwise) are purged
  after 12 months. Defaults to a dry run — `python -m scripts.data_retention`
  reports what it would do; `--execute` actually applies it. Not wired
  into a scheduler yet — same "code is real, the schedule is a manual
  Render Cron Jobs step" shape as `scripts/reconcile_payments.py`.
- **PII minimisation audit (step 7.a.ii, done as a review, not a rewrite)**
  — every model was reviewed field-by-field for personal data that isn't
  genuinely needed. Conclusion: no field was found that should be removed
  outright — everything stored (skills, portfolio links, company
  registration numbers, message content, private rating comments, and so
  on) is directly load-bearing for a feature that needs it. The actual
  minimisation gap wasn't "fields that shouldn't exist," it was **retention
  with no time limit** — fixed by 7.a.i above, not by deleting fields.
- **Explicit consent capture (step 7.b.i)** — `StudentRegister.data_sharing_consent`
  is a required (not optional, not pre-ticked) field; omitting it is a
  422, not a silent default. Recorded as a timestamp
  (`StudentProfile.data_sharing_consent_at`), not just a boolean, so there's
  a durable record of *when* consent was given. **A known, honest gap**:
  a student JIT-provisioned via university SSO (2.b) never sees this
  wording at all, so `data_sharing_consent_at` is deliberately left unset
  for them rather than backfilled with a fabricated timestamp — closing
  this needs a real one-time post-login consent screen, a Workstream 5
  (frontend) concern, same shape as the CAPTCHA widget/SSO metadata-upload
  gaps.
- **Cookie/tracking consent banner (step 7.b.ii) — done, because it
  genuinely doesn't apply.** This step is explicitly conditional in the
  plan ("required *if* any analytics or non-essential cookies are used").
  Checked directly: authentication here is bearer-token-in-header (see
  `static/app/js/api.js`), not cookie-based, and there is no analytics or
  tracking script anywhere in `app/` or `static/`. Nothing to build until
  that changes — revisit this the moment analytics or cookies are ever
  actually added, not before.
- **Personal data export (`GET /privacy/export`, step 7.c.i)** — a
  self-service GDPR Subject Access Request export as JSON, covering
  everything CAPLink holds that constitutes or relates to a user's
  personal data: account/profile fields, applications, contracts and
  milestones, every message in a thread they're part of (both sent and
  received — a two-party conversation is legitimately part of both
  parties' own data), ratings given and received, recommendation history,
  and registered devices. See `app/services/privacy.py::export_user_data`.
- **Account deletion (`DELETE /privacy/account`, step 7.c.ii)** — requires
  re-entering the current password first (same "sensitive action needs
  reauth" pattern as MFA disable requiring a valid TOTP code), then
  **anonymizes rather than hard-deletes**. This is a deliberate design
  decision, not a shortcut: a contract, rating, or message a user was
  party to also legitimately belongs to the *other* party's own record
  (their own contract history, their own received rating) — hard-deleting
  the `User` row would either cascade-destroy that other party's data too,
  or simply fail on a foreign-key constraint. GDPR's right to erasure
  doesn't require deleting data another party has a legitimate ongoing
  interest in; it requires erasing what identifies *this* person. So
  deletion clears email/name/password/MFA secrets/device push tokens (a
  physical-device identifier with no reason to survive account closure)
  and a student's portfolio links, while leaving the structural rows
  (contracts, ratings, message content) intact but now pointing at an
  anonymized account. See `app/services/privacy.py`'s module docstring
  for the full reasoning.
- **Encryption at rest (step 7.d.i) — done, confirmed not assumed.**
  Render Postgres databases are encrypted at rest with AES-256 by
  default, covering primaries, replicas, and backups alike, with no
  configuration needed — confirmed via Render's own documentation and
  community support answers, not just taken on faith.
- **TLS everywhere + HSTS (step 7.d.ii)** — TLS termination itself is
  Render's job, not this app's: every `*.onrender.com` service and any
  custom domain gets HTTPS automatically at Render's edge, confirmed via
  Render's own documentation. What Render does *not* do on its own is
  tell a returning browser "never fall back to plain HTTP for this origin
  again" — that's what the `Strict-Transport-Security` header does, and
  it has to come from the application: `app/core/security_headers.py`'s
  `HSTSMiddleware`, added in every environment except `development`
  (a local `http://localhost` origin shouldn't get a header that assumes
  TLS is terminating somewhere in front of it).
- **UK/EU data residency (step 7.d.iii) — NOT done, a real gap, not
  quietly worked around.** `render.yaml` currently hosts both
  `caplink-api` and `caplink-staging-db` in **Oregon, USA** — confirmed
  directly from the blueprint, not assumed. For a UK-focused platform
  processing UK university students' personal data, hosting outside the
  UK/EU raises genuine international-data-transfer questions under
  UK GDPR that a university's own data-protection office will ask about
  directly during due diligence. Render does offer a Frankfurt, Germany
  region (confirmed via Render's own regions documentation) as the
  realistic EU alternative. **Not changed here** — moving region means
  recreating the database (the same region-must-match gotcha already
  documented in `render.yaml` from step 1.a.iv, this time on a database
  that now holds real staging data, however sparse) and is a genuine
  infrastructure decision for the account owner to make deliberately, not
  something to change unprompted mid-session. Flagged clearly rather than
  left to be discovered later during a real DPIA.

## Frontend web application (design system, portals, accessibility)

Technical Implementation Plan Workstream 5. **One deliberate deviation from
the plan's literal wording, decided with the account owner rather than
silently substituted**: the plan asks for the design system/components "as
production React components." There is no Node.js/npm anywhere this project
has been built or deployed from, so a React build could never actually be
installed, compiled, or verified in this environment — the choice was
between building something unverifiable, or extending the existing
no-build-step vanilla-JS reference UI (`static/app/`) to real production
quality using the same architecture it already uses. The account owner
chose the latter explicitly. The component-library *discipline* the plan
actually cares about — one canonical definition per reusable UI pattern,
reused everywhere it appears, not copy-pasted — is delivered the same way
either way; only the implementation technology differs.

- **Design tokens (5.a.i)** — `static/app/css/tokens.css`. Pulls the colour
  palette that was already living, unlabelled, inline in `app.css`'s
  `:root` block into one documented file, and adds spacing/radius/type/
  motion/elevation scales `app.css` previously hard-coded ad-hoc pixel
  values for instead.
- **Component library (5.a.ii)** — `static/app/js/components.js`. Exported
  render functions for the plan's four named components: `renderMatchDial`
  (an SVG circular score indicator, replacing the old plain `.score-track`
  bar for this specific use), `renderProjectCard`/`renderStudentCard`
  (formalizing what already existed ad-hoc as `.item-card` markup
  duplicated across `student.js`/`business.js`), and `openRatingModal` (a
  real `<dialog>`-based star-rating modal, replacing an inline
  number-input form that lived directly in `shared/contracts.js`).
  `student.js` and `shared/contracts.js` were refactored to actually call
  these instead of keeping their own duplicate markup.
- **Student/Business/University-Admin portals (5.b–5.d)** — nearly all of
  this already existed functionally (see "The full app" in
  `caplink/CLAUDE.md`); this workstream's job was formalizing it against
  the new component library and closing real gaps found along the way, not
  building three portals from scratch:
  - Two **real, pre-existing production bugs** were found and fixed while
    doing this: SSO login and Stripe Connect onboarding both redirected to
    `/app/app.html`, a file that has never existed (should be
    `/app/index.html`) — and even had that redirect worked,
    `static/app/js/main.js` never actually implemented the
    `consumeSsoHandoff()` function its own `saml.py` docstring claimed
    existed, meaning **SSO login was completely non-functional end-to-end**
    until this session. Both are fixed now (`app/services/stripe_connect.py`,
    `app/api/v1/endpoints/saml.py`, `static/app/js/main.js`).
  - **5.c.ii (match-explanation drill-down)** needed a genuinely new
    backend endpoint — the existing `GET /projects/{id}/match-explanation`
    is student-only (scores the calling student, no `student_id`
    parameter), so a business could never call it for a specific shortlist
    candidate. Added `GET /projects/{id}/shortlist/{student_id}/explanation`
    (`app/api/v1/endpoints/applications.py`), reusing the same scorer and
    the same safeguarding-visibility check `GET .../shortlist` already
    applies, and wired a "View shortlist" / "Why this match?" flow into
    `business.js` to actually call it.
  - **5.d.ii (band/category permission editor)** was checked against the
    visual mockup in `../caplink-university-landing.html`'s "band control
    panel" section — the existing agreement-approval UI in
    `university-admin.js` already uses the same `.permit-pill`/`.lc-row`
    visual vocabulary as that mockup for the read-only summary; judged
    functionally and visually complete, not reworked further.
  - **5.d.iii (employability reporting dashboard) — not started,
    genuinely blocked, not deprioritised.** P1/Large in the plan itself,
    and zero backend aggregation exists to report on yet (only stray
    docstring mentions of "employability" elsewhere in the codebase). Left
    for a session with more time/backend design work, matching the plan's
    own P0-before-P1 sequencing.
- **Accessibility conformance, WCAG 2.2 AA (5.e)** — see
  `static/app/accessibility.html` (linked from the footer of `/app`) for
  the full statement. Short version: manual expert review substitutes for
  an automated axe-core audit (5.e.i) since no Node/browser toolchain is
  available to run one in this environment. One real keyboard-accessibility
  bug was found and fixed doing this review: the messages thread list in
  `shared/messaging.js` rendered each conversation as a `<div>` with only a
  click handler — not Tab-reachable, not Enter/Space-activatable. Fixed by
  making it a real `<button>` (with matching CSS to undo default button
  chrome). New custom widgets (the match dial, the star-rating picker) got
  explicit ARIA roles/labels from the start rather than needing a
  retrofit. Known, documented gaps: no screen-reader read-through of the
  most data-dense screens yet, and the tab strips are keyboard-operable
  real `<button>`s but don't carry the full ARIA tabs pattern
  (`role="tablist"/"tab"`) — both listed on the statement page itself
  rather than left undocumented.

**Verification for this workstream**: backend changes (the new shortlist
explanation endpoint, the SSO/Stripe redirect fixes) were verified via
`TestClient` — including a real cross-business ownership check (a second
business gets a genuine 404, not just a review-time assumption) — plus the
full `ruff`/`mypy`/`pytest` suite (0 errors, 105/105 passing). **Frontend
changes could not be verified in a real browser this session** — the
claude-in-chrome extension wasn't connected — so the JS was instead
verified by: parsing every changed file with a real ES-module-aware parser
(`esprima`, installed temporarily for this check only) to catch syntax
errors; confirming every CSS class the new JS references
(`.match-dial`, `dialog.modal`, `.star-picker`, `.item-card.clickable`,
`.lc-row`) actually exists in `app.css`; and serving every changed/new
static file through a real running instance of the app to confirm none
404. This is a real gap relative to this project's usual "click through it
in an actual browser" standard for frontend work — worth doing a real
browser pass the next time the extension is available, rather than
assuming this substitute caught everything a real click-through would.

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

`.github/workflows/ci.yml` runs five independent checks on every pull request (and on
pushes to `main`, as a safety net): `ruff check .` (lint), `mypy app/ scripts/`
(type-check), the full `pytest` suite, `bandit`/`pip-audit` (SAST and dependency
scanning — see "Security scanning" below), and a Docker image build. Config for lint/
type-check lives in `pyproject.toml` — notably `line-length = 135` (matches this
codebase's existing style rather than forcing a repo-wide reformat) and a deliberately
narrow `select = ["E", "F"]` (flake8-bugbear's `B008` would otherwise flag every single
FastAPI `Depends(...)` default argument as an anti-pattern, which is just how FastAPI
dependency injection works).

### Testing — three layers, not one

Technical Implementation Plan 8.a. Until 2026-09-10 this project's entire test suite —
however large it grew — was unit/service-level only: every test called a service
function directly with a bare SQLAlchemy session (`db_session` in `tests/conftest.py`),
never through the actual FastAPI app. Every "verified via TestClient end-to-end" claim
scattered through this project's history (SSO, Stripe payments, the contract-ownership
authorization fix, CAPTCHA) was a real, thorough, one-off manual script run once during
that session and then thrown away — never a permanent regression test. `tests/conftest.py`'s
`client` fixture (a real `TestClient(app)` with the `get_db` dependency overridden to an
isolated in-memory database — see the fixture's own docstring for why it deliberately
never triggers the app's startup lifespan) closes that gap:

- `tests/test_golden_path_e2e.py` — the core product loop end-to-end: post a project,
  apply, get hired via a milestone contract, pay out both milestones through the
  (simulated) escrow flow, mutual blind ratings. Plus the safeguarding gate rejecting an
  unapproved business, and a regression test for the real contract-ownership
  authorization bug found and fixed during Workstream 3.
- `tests/test_messaging_e2e.py` — thread creation, the off-platform-contact flagging
  heuristic actually flagging a phone number/suspicious phrase, a third party correctly
  forbidden from a conversation, and a real 429 from the messaging rate limit.
- `tests/test_saml_endpoints_e2e.py` — SP metadata generation and the "SSO not enabled"
  404 on both the login and ACS routes. **Known, deliberately flagged gap**: the actual
  assertion-consumer path (a real IdP posting a signed SAML response) still isn't covered
  by a permanent test — that needs a hand-built, XML-DSig-signed assertion against a
  self-signed test certificate, real work verified once manually (see this file's Epic 2.b
  history) but not yet rebuilt as a lasting regression test.
- `tests/test_mfa_e2e.py`, `test_privacy_e2e.py`, `test_agreements_and_audit_log_e2e.py`,
  `test_auth_session_e2e.py`, `test_applications_e2e.py`, `test_local_search_e2e.py`,
  `test_mobile_and_verification_e2e.py`, `test_profile_updates_e2e.py` — added across later
  sessions, covering TOTP MFA's full HTTP cycle, GDPR export/deletion, the safeguarding
  gate's approve/reject decision plus the audit log, token refresh and password change, the
  business-side hiring-decision surface, postcode-radius local search, mobile device
  registration, the real (non-dev) email-verification token flow, and profile updates.
  Remaining gaps, left deliberately rather than silently: `GET /projects/mine`,
  `GET /ratings/pending`/`mine`, the payments status-check endpoints, and employer-
  suggestion feedback are still untested at the HTTP layer — read-only listings, lower risk
  than everything above.

`tests/test_*.py` outside those files remain unit/service-level by design — fast,
focused, no HTTP/app overhead for testing a scoring algorithm or a password policy.

**Frontend unit tests (8.a.ii) — done as of 2026-09-11.** Vitest + jsdom, no build step
(`static/app/index.html` still loads plain `<script type="module">` tags directly — this
only adds a test runner, never a bundler/compiler). Genuinely blocked until this session:
no Node.js/npm had existed anywhere in this project's history until Phil installed it via
`nvm` specifically to unblock this step. Run with `npm test` (see `package.json`); CI runs
it on every push/PR as the `frontend-test` job. Coverage so far focuses on the three
highest-value, most-reused files rather than every page module: `static/app/js/dom.js`
(`dom.test.js` — most notably `esc()`, this app's only defence against stored XSS in every
render function, with a permanent regression test reproducing the exact payload that found
a real stored-XSS bug in `contracts.js` during Epic 2.c.ii), `api.js` (`api.test.js` —
JWT decoding, session state, the `fetch` wrapper's error handling), and `components.js`
(`components.test.js` — the reusable component library itself, including `openRatingModal`'s
real `<dialog>` interaction; needed a small `showModal()`/`close()` polyfill in
`static/app/js/test-setup.js` since jsdom doesn't implement either as of the version this
project uses). The large page-specific modules (`main.js`, `student.js`, `business.js`,
`university-admin.js`) remain untested — a real, acknowledged gap, not an oversight;
they're mostly DOM wiring around the tested components/helpers rather than standalone
logic, so the return on testing them directly is lower than for the files covered so far.

### Security scanning

Technical Implementation Plan 8.c.i. `bandit` (static analysis) and `pip-audit`
(dependency vulnerabilities) run in CI on every push/PR, failing the build on any real
finding. `[tool.bandit]` in `pyproject.toml` skips rule `B101` (`assert_used`) project-wide
— this codebase's ~40 documented `assert x is not None, "<why this can't actually be
None>"` invariant guards (added during Epic 1.b to narrow types for mypy while
documenting a real invariant) aren't the "asserts vanish under `python -O`" risk that rule
warns about; this app is never run with `-O`. Three other one-off false positives
(`B105`/`B106` on JWT `token_type` string literals and a comparison *against* the known
dev placeholder secret, not a use of it) are suppressed individually with inline
`# nosec` comments and a reason, not swept away project-wide.

One dependency vulnerability is a deliberate, documented, ongoing exception rather than
fixed or silently ignored: `ecdsa` (a transitive dependency of `python-jose`) has a known,
upstream-declared-wontfix Minerva timing attack (`PYSEC-2026-1325`) against ECDSA
signing. CAPLink's JWTs are always signed `HS256` (see `Settings.ALGORITHM` in
`app/core/config.py`) — the vulnerable ECDSA code path is never actually exercised by
this app. CI's `pip-audit` step explicitly ignores only that one ID
(`--ignore-vuln PYSEC-2026-1325`); any other CVE still fails the build. **Revisit this if
`ALGORITHM` is ever changed to an ES-family algorithm.**

### Load testing & performance

Technical Implementation Plan 8.b. `GET /projects/feed` (a student's ranked, safeguarded
project feed) is the most computationally interesting endpoint in the API — it runs the
full matching engine across every visible open project on every request, not just the
page returned. Profiling it under a realistic volume (~100 open projects across 20
businesses) surfaced a real N+1 query pattern: `collaborative_score` (the matching
engine's "students like you also succeeded here" factor) ran its own "accepted
applications in this category" query **once per candidate project**, so ~100 candidates
sharing ~8 categories issued the same handful of queries up to a dozen times over each —
plus a second, nested per-accepted-application `StudentProfile` lookup inside that. Fixed
in `app/services/matching/collaborative.py`: `fetch_accepted_pairs_by_category` now
runs **one** query for every category a batch actually needs (both `Application` and its
`StudentProfile` joined directly, no per-row follow-up query), and
`rank_projects_for_student`/`rank_students_for_project` compute it once up front and
hand each candidate its own slice. `collaborative_score` itself is unchanged for
single-score callers (e.g. the business-side match-explanation drill-down) — they simply
don't pass a pre-fetched cache and it queries exactly as it always did, just without the
old inner per-application lookup either way.

Measured effect (via `cProfile`, same seeded ~100-project volume): a single
`rank_projects_for_student` call dropped from **~100 DB round-trips to 1**, and wall time
for the ranking pass alone from 56ms to 34ms (~40% faster). Concurrent-load numbers
(via a simple `httpx` + `ThreadPoolExecutor` script, 50 requests at concurrency 10)
stayed noisy and high (p95 in the 500ms range) even after the fix — this environment's
SQLite backend serializes concurrent access far more coarsely than the real Postgres
staging/production database does, so those absolute concurrent-latency numbers are a
dev-only artifact, not a representative production measurement. **Follow-up, not done
here**: re-run the same load test against a real Postgres instance (e.g. via
`docker-compose.yml`, itself still unverified — no Docker in this environment) once one
is available, to get a number that actually reflects production. The remaining
single-request cost (~60% of the 34ms) is `weighted_skill_overlap`'s `difflib`-based
fuzzy skill matching — legitimate, CPU-bound, and not concurrency-related; a reasonable
target for a future optimization pass but not the dominant cost that profiling found here.

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

## Database backups

**Not automated** — `caplink-staging-db` runs on Render's free Postgres tier, which
doesn't include the automated daily backups / point-in-time recovery that Render's paid
Postgres plans do. Deliberately left this way rather than building a stopgap: there's no
real data worth protecting yet on a disposable staging demo, and a real backup strategy
belongs on a real (paid) database anyway — revisit once one exists.

**Manual backup** (works today, on any plan):

```bash
# DATABASE_URL here should be the database's *External* connection string
# (from Render's dashboard) if running this from outside Render's network.
pg_dump "$DATABASE_URL" -F custom -f "caplink_backup_$(date +%Y%m%d).dump"
```

**Restore** (the drill this step calls for — always into a *separate*, empty database,
never over a live one without a very good reason and an even better backup of what
you're about to overwrite):

```bash
createdb caplink_restore_test
pg_restore -d caplink_restore_test caplink_backup_YYYYMMDD.dump
```

Then spot-check with `psql caplink_restore_test` — row counts on a few key tables
(`universities`, `users`, `contracts`) should match what the backup's source had.

This is a documented procedure, not one that's actually been run — no Docker/Postgres was
available in the environment it was written in (same caveat as the Dockerfile above).
Worth actually running once, deliberately, before trusting it against real data.

## API documentation

Technical Implementation Plan 8.d.ii. FastAPI auto-generates interactive docs at `/docs`
(Swagger UI) and `/redoc` from every endpoint's type hints and docstring — no separate
docs site to maintain. "Polish" here meant finding and fixing the endpoints where that
auto-generation had nothing real to work with: a scan of the generated OpenAPI spec found
**26 of 67 endpoints** (register/login, creating a project, applying, creating a
contract, submitting a rating, sending a message, and others) had no real description at
all — just FastAPI's default title-cased-function-name summary (e.g. "Create Contract"
with nothing else). Every one of those 26 now has a short, real docstring explaining what
it actually does, any non-obvious behaviour (e.g. that `/auth/login` can return an MFA
challenge instead of tokens, or that `/messages` scans content for off-platform-contact
patterns), and a pointer to the relevant README section where one exists. Re-scanning
after confirms zero endpoints left with a thin description.

## Penetration-test scope and environment

Technical Implementation Plan 8.c.ii. This project has not had a professional
penetration test — that needs a licensed third-party tester, a genuine external step,
not something to fake here. What follows is the scoping brief a real engagement would
need, prepared in advance so booking one is a phone call, not a discovery exercise.

**In scope**:
- The API itself (`app/api/v1/`) — auth, the safeguarding access-control gate, payments/
  escrow, messaging, SAML SSO, the matching engine's endpoints.
- The reference web UIs (`static/app`, `static/demo`) as a client of that API.
- Session/token handling (JWT access+refresh, MFA challenge tokens, SAML assertions).

**Out of scope**:
- Stripe's, Render's, and any other third party's own infrastructure — a real pen test
  targets *this* application's use of those services (e.g. can a user manipulate a
  webhook payload, not "is Stripe's API secure").
- Denial-of-service / load testing beyond what "Load testing & performance" above already
  covers — a dedicated DoS test needs separate authorization and scheduling given the
  free-tier hosting this currently runs on (see "What's stubbed vs. production-ready").
- Physical/social-engineering testing — not applicable to a solo-founder pre-pilot project.

**Environment**: staging (`caplink-api.onrender.com`, see "Environments" above) is the
correct target, never production (none exists yet). Staging's database currently holds
only seeded demo/test data, not real students' or businesses' information — confirm this
is still true immediately before any engagement starts, since that could change once a
real pilot begins.

**Test accounts**: the three seeded demo accounts (`aisha.rahman@manchester.ac.uk` /
`hello@datacraft-analytics.com` / `admin@manchester.ac.uk`, password `ChangeMe123!` for
all three — see "Quickstart") cover the student/business/university-admin roles. A
platform-admin account (the fourth role, gating `/audit-log` and university onboarding)
has no self-registration path; request one be created directly in the database for the
engagement, and anonymised/rotated afterward.

**Known, already-documented weak points worth a tester's specific attention** (not
hidden — flagging them saves a tester's time re-discovering what's already known):
the UK/EU data residency gap (staging is in Oregon, USA — see "Data protection & privacy
engineering"), the unverified Dockerfile/backup-restore procedures (never actually run —
see "Rollback procedure" and "Database backups"), and the SAML assertion-consumer path's
test coverage gap (see "Testing — three layers, not one" above) — a real tester attacking
the ACS endpoint directly is, if anything, the closest thing to that missing coverage
this project currently has.

## Operational runbooks

Technical Implementation Plan 8.d.i. Concrete steps for the incidents most likely to
actually happen, cross-referencing the detailed sections elsewhere in this README rather
than repeating them.

**Deploy is failing / service won't start**: check Render's deploy logs first — the two
most common real causes so far have both been migration-related: a NOT NULL column added
without a `server_default` failing against a database with existing rows, or (once, for a
brand-new Postgres enum type) `add_column` needing the enum type created first via
`sa.Enum(...).create(op.get_bind(), checkfirst=True)` — see "Database migrations
(Alembic)" and `caplink/CLAUDE.md`'s migration history for the exact failure signatures.
If the previous deploy was healthy, roll back immediately (see "Rollback procedure")
before debugging further — a failing deploy on `main` blocks every subsequent push.

**A migration applied badly against a database with real rows**: `alembic downgrade -1`
reverses it (see "Rollback procedure" for the Postgres-enum caveat), but check first
whether the migration's `upgrade()` already committed partial damage — Postgres's
transactional DDL means most migrations roll back cleanly on failure, but a downgrade
after a *successful*-but-wrong migration only reverses schema, not any data changes an
endpoint made against the new columns in between.

**A user reports they can't log in**: check `failed_login_attempts`/`locked_until` on
their `User` row first (progressive lockout — see "Auth hardening") before assuming a
password issue; the account unlocks itself once the backoff window passes, or can be
cleared directly in the database for a genuine false positive. If they have MFA enabled
and lost their device, a `/mfa/disable` call needs a valid code — recovery for a genuinely
locked-out admin means clearing `totp_enabled`/`totp_secret`/`mfa_backup_codes` directly
in the database after verifying their identity out-of-band, since there is no self-service
"I lost my authenticator" flow.

**Suspected credential leak (SECRET_KEY, Stripe keys, DB password)**: rotate the specific
secret in Render's dashboard immediately (Environment tab — see `render.yaml`'s `sync:
false` entries for which ones live there) and redeploy. Rotating `SECRET_KEY` invalidates
every existing access/refresh token instantly — every logged-in user is signed out, which
is the correct trade-off for an actual leak. Check `caplink/CLAUDE.md` for the one known
historical near-miss (a real DB password briefly sitting in a local `.env` file, never
reaching git) before assuming a leak is unprecedented.

**A milestone payment is stuck / a webhook seems to have been missed**:
`scripts/reconcile_payments.py` (read-only) compares every `Milestone` against Stripe's
live `PaymentIntent` record and logs drift — run this first rather than guessing. See
"Payments & payroll" for the escrow mechanism itself; a milestone stuck in `submitted`
with no matching Stripe status usually means the `approve-and-pay` call raised and was
never retried, not a webhook problem specifically (webhooks here only cover
`charge.dispute.created`).

**Error rate spike / Sentry alert**: `SENTRY_DSN` (see "Observability") captures every
unhandled exception with `environment` tagged — filter by that first. Structured JSON
request logs (`method`/`path`/`status_code`/`duration_ms` — see the same section) are the
next place to look for a pattern (one endpoint, one status code, one time window).

## Admin & moderation playbooks

Technical Implementation Plan 8.d.iii. For whoever holds the `platform_admin` or
`university_admin` role — the real moderation/decision surfaces that exist today, not a
generic content-moderation policy for features this platform doesn't have.

**Deciding a business partnership agreement request** (university admin,
`university-admin.js`'s Partnerships tab or `PATCH /universities/{id}/business-agreements/{id}`
directly): approve only the specific year-bands and project categories the business has
actually been vetted for — the safeguarding gate enforces whatever is selected here
literally, with no implicit trust beyond it. Every decision is written to the audit log
automatically (see below); there's no need to separately document *that* a decision was
made, only to make the right one.

**Reviewing a flagged message** (`messages.py`'s off-platform-contact heuristic — phone
numbers, external emails, phrases like "pay you directly" or "whatsapp me"): flagged
messages are visible via `GET /messages/threads/{id}` like any other, with `is_flagged`/
`flagged_reason` on the record (the *sender* never sees the reason back — see "Testing"
above). There is currently no dedicated admin UI listing all flagged messages platform-
wide; reviewing one today means already knowing which thread to look at (e.g. from a
user report). **Known gap**: a "flagged messages" admin queue, analogous to the audit
log, would need building — not done as part of this pass.

**Reading the audit log** (`GET /audit-log`, platform-admin only): write-once, covers a
university admin's agreement decisions, a platform admin onboarding a new university, and
SAML config changes (see `caplink/CLAUDE.md`'s Epic 2.c/2.d entry for exactly what is and
isn't logged, and why "rating overrides"/"account suspensions" — mentioned in the original
plan text — aren't, since neither is a real feature here). Use this to answer "who
approved/changed X and when," not as a general activity feed.

**A milestone dispute** (a business disputes work already paid for, or a student disputes
a rejection): `POST .../milestones/{id}/refund` reverses a *captured* payment (money
already moved) and auto-reverses the associated Stripe transfer; `POST .../reject` cancels
a *submitted-but-unpaid* milestone's authorization outright, no money ever having moved.
Check which state the milestone is actually in (`GET /contracts/mine`) before choosing —
refunding a never-captured milestone or rejecting an already-paid one will simply fail,
not silently do the wrong thing, but knowing which to call saves a round trip. Stripe's
own `charge.dispute.created` webhook additionally marks a milestone `DISPUTED`
automatically if a business's cardholder disputes the charge directly with their bank,
independent of anything either party does in-app.

**A university's license needs suspending** (non-payment, contract end, a serious
safeguarding failure on their end): `University.license_status` — no dedicated endpoint
exists for this yet; it's a direct database change today. `is_license_active()`
(referenced throughout `auth.py`/`projects.py`) is the single source of truth every
access-control check defers to, so flipping this one field is sufficient to lock out every
student/business tied to that university without needing to touch individual accounts.
