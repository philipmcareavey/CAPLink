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
- **Stripe Connect** (integration point) — escrow milestone payments
- **Firebase Cloud Messaging** (integration point) — mobile push notifications

## Quickstart

```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt --break-system-packages   # omit the flag in a normal venv

cp .env.example .env
# edit .env — SQLite works out of the box for local dev, no changes needed

# create demo data: a licensed university, an approved business agreement,
# a student, a business, and an open project
python -m scripts.seed_demo_data

uvicorn app.main:app --reload
```

Visit `http://localhost:8000/docs` for interactive Swagger docs.

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

`app/services/matching.py` implements **Phase 1** from the implementation plan:
explainable, rules-based scoring on skills, rate, availability, and degree relevance.
Every recommendation shown is written to `RecommendationLog` (model), including the
plain-English reasons — this is the training data Phase 2 (collaborative filtering)
and Phase 3 (embedding-based semantic matching) will consume, without needing to
change any calling code.

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

## University licensing endpoints

- `POST /api/v1/universities` (platform-admin only) — onboard a new licensed institution
- `GET /api/v1/universities/{slug}/public` — unauthenticated branding lookup, powers each
  university's landing page at `{slug}.caplink.io`
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
