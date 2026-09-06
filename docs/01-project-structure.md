# Project Structure

## What this codebase is

CAPLink is a **backend only** — there is no website or app in this repository. It's
a FastAPI server that exposes a JSON API over HTTPS. Universities, students,
businesses, and (eventually) a mobile app all talk to this one server. Right now,
the only way to *see* it working is:

- the interactive API docs at `/docs` (see
  [04-using-the-api-docs-ui.md](04-using-the-api-docs-ui.md)), or
- calling the API directly with `curl` / Postman / a script.

## The core idea, in one paragraph

A **university** licenses CAPLink (like licensing Blackboard/Canvas). Its careers
team decides, per business, exactly which year-groups of students that business is
allowed to see and which categories of project it's allowed to post. A **business**
can do nothing with a university's students until that university has explicitly
approved it. Once approved, the business posts paid **projects**, **students**
apply, a **contract** with milestone-based payments is formed, work happens, both
sides **rate** each other, and a simple **matching engine** recommends the best
project↔student pairings and explains *why* in plain English.

## Folder layout

```
caplink/
├── app/
│   ├── main.py                 FastAPI app object, startup hook, CORS, health check
│   ├── core/
│   │   ├── config.py           All settings, read from .env (Settings class)
│   │   └── security.py         Password hashing (bcrypt) + JWT access/refresh tokens
│   ├── db/
│   │   ├── base_class.py       SQLAlchemy declarative Base + shared mixins (UUID id, timestamps)
│   │   ├── session.py          Engine + SessionLocal + get_db() FastAPI dependency
│   │   └── migrations.py       Runs the Alembic chain on startup; stamps pre-Alembic databases instead of re-creating tables
│   ├── models/                 SQLAlchemy ORM classes — the actual database tables
│   │   ├── enums.py            Every enum used across the whole system (roles, statuses, bands...)
│   │   ├── user.py             User, StudentProfile, BusinessProfile
│   │   ├── university.py       University (a licensed tenant)
│   │   ├── policy.py           UniversityBusinessAgreement (the safeguarding gate)
│   │   ├── project.py          Project
│   │   ├── application.py      Application (a student applying to a project)
│   │   ├── contract.py         Contract, Milestone
│   │   ├── rating.py           Rating (mutual, blind-until-both-submit)
│   │   ├── message.py          MessageThread, Message
│   │   ├── device.py           Device (push notification registration)
│   │   └── recommendation.py   RecommendationLog (every match ever shown, for training data)
│   ├── schemas/                Pydantic models — define the JSON shape of requests/responses
│   │   (one file per resource, named to match models/)
│   ├── services/                Business logic that isn't tied to one HTTP endpoint
│   │   ├── access_control.py   THE safeguarding gate — every student↔business check goes through here
│   │   ├── matching.py         Rules-based scoring: how well does a student fit a project?
│   │   └── notifications.py    Push notification abstraction (currently just logs; Firebase is a stub)
│   └── api/
│       ├── deps.py             Shared FastAPI dependencies: get_current_user, require_<role>, Pagination
│       └── v1/
│           ├── api.py           Combines every endpoint router into one api_router
│           └── endpoints/       One file per resource — the actual HTTP routes
│               ├── auth.py           register/login/refresh
│               ├── universities.py   onboarding + public branding lookup
│               ├── policies.py       business↔university agreements (the approval workflow)
│               ├── students.py       student's own profile
│               ├── businesses.py     business's own profile
│               ├── projects.py       post a project, get the student's suggested-projects feed
│               ├── applications.py   apply to a project, view shortlist, change application status
│               ├── contracts.py      create contract, accept terms, submit/pay milestones
│               ├── ratings.py        mutual ratings after a contract
│               ├── messages.py       in-app messaging with off-platform-contact flagging
│               ├── recommendations.py  feedback on recommendations + "employer suggestions"
│               └── mobile.py         device registration + combined home-screen payload
├── scripts/
│   └── seed_demo_data.py       Creates one working demo tenant end-to-end (see Getting Started)
├── alembic/
│   ├── env.py                  Points Alembic at Base.metadata + settings.DATABASE_URL
│   └── versions/                One file per schema migration, in order
├── alembic.ini                  Alembic config (sqlalchemy.url here is unused — env.py overrides it)
├── requirements.txt             Pinned Python dependencies
├── .env.example                 Template for local config — copy to .env
└── docs/                        You are here
```

## How a request flows through the code

Take `GET /api/v1/projects/feed` (a student's home feed) as a concrete example —
this touches almost every layer:

1. **`app/main.py`** has mounted `api_router` under `/api/v1`, so the request
   reaches **`app/api/v1/endpoints/projects.py`**.
2. The endpoint depends on `require_student` (from **`app/api/deps.py`**), which
   in turn depends on `get_current_user` — this decodes the JWT bearer token
   (via **`app/core/security.py`**), loads the `User` row, and rejects the request
   with 401/403 if the token is missing/invalid or the role is wrong.
3. It loads the student's own `StudentProfile` and every currently `OPEN`
   `Project` (both are **`app/models/`** SQLAlchemy classes, queried via the
   `Session` yielded by **`app/db/session.py`**'s `get_db()`).
4. **`app/services/access_control.py`**`.filter_projects_visible_to_student(...)`
   strips out any project the student isn't allowed to see (wrong university,
   wrong year-band).
5. **`app/services/matching.py`**`.rank_projects_for_student(...)` scores and
   sorts what's left, returning a score (0–1) and plain-English reasons per
   project.
6. The endpoint pages the ranked list (`app/api/deps.py`'s `Pagination`), writes
   a `RecommendationLog` row for every project shown (so the matching engine has
   training data later), and serialises the result using the
   **`app/schemas/project.py`**`.ProjectWithMatch` Pydantic model — this is the
   JSON shape the client actually receives.

Every other "does X touch a student" endpoint (shortlists, applying, messaging)
follows the same shape: **endpoint → role check → access_control gate →
model query → schema serialisation.**

## The safeguarding model (the most important design decision)

A business has **zero visibility** of any student at a university until:

1. A `UniversityBusinessAgreement` exists between that business and that
   university, **and**
2. its `status` is `APPROVED`, **and**
3. the student's `band` (`year_1`, `year_2`, ... `postgrad_research`,
   `recent_alumni`) is inside that agreement's `allowed_bands`, **and**
4. for *posting* a project: the project's `category` is inside the agreement's
   `allowed_categories`.

This is enforced in exactly one place — `app/services/access_control.py` — and
every endpoint that could leak student data calls into it rather than
re-implementing the rule. A university admin manages this via
`PATCH /api/v1/universities/{id}/business-agreements/{id}`.

## The matching engine

`app/services/matching.py` is deliberately simple and fully explainable
("Phase 1" of a longer roadmap): it scores skill overlap, rate compatibility,
availability, and degree relevance, and always returns *why* a score is what it
is (e.g. `"Skill match: python, sql"`, `"Within budget"`). Every recommendation
shown is logged to `RecommendationLog`, along with whatever the user did next
(`applied` / `dismissed` / `messaged`) via
`POST /api/v1/recommendations/{log_id}/feedback` — that log is meant to become
the training data for a smarter (collaborative-filtering / embeddings-based)
version later, without changing any of the calling code.

## What's real vs. stubbed

**Fully working:** registration/login/JWT refresh, multi-tenant university
licensing, the safeguarding access-control gate, the matching engine +
recommendation logging, project posting, applications, contracts + milestones,
mutual blind ratings, in-app messaging with off-platform-contact flagging,
mobile device registration + combined home payload, Alembic-managed schema
migrations (`alembic/versions/` — applied automatically on startup via
`app/db/migrations.py`, which is why local dev still needs zero setup on a
fresh clone), structured JSON logging for every log line including uvicorn's
own (`app/core/observability.py`), and auth hardening — password complexity
+ breach checking, progressive account lockout + per-IP rate limiting, a
real confirmation-link email verification flow, TOTP MFA for admin
roles, and a real SAML 2.0 SSO flow per university, with JIT student
provisioning (see README's "Auth hardening" section for the full picture).

**Stubbed (clearly marked in code, safe to demo without them):**
- **Payments** — `approve_and_pay_milestone` sets a fake
  `stripe_payment_intent_id` instead of calling Stripe.
- **Push notifications** — `notifications.py._send_push` just logs instead of
  calling Firebase.
- **Verification emails** — `email.py._send_email` just logs instead of
  calling a real ESP (SendGrid/Postmark/SES); the confirmation-link flow
  itself is fully real, only actual delivery is stubbed.
- **University *institution* verification** — real SAML SSO now exists
  (`app/services/saml.py`, `app/api/v1/endpoints/saml.py`) for any
  university that configures its IdP details, but it's opt-in per
  university (`saml_enabled`); a university that hasn't set it up still
  falls back to a student's email simply needing to end in
  `@<university.domain>` to confirm *which* university they belong to.
  Both are separate from (and in addition to) the real per-account email
  confirmation flow.
- **Error tracking** — Sentry integration is wired up (`app/core/observability.py`)
  but inactive until `SENTRY_DSN` is set to a real project's DSN.
- **Uptime monitoring** — not configured anywhere; needs an external service
  (e.g. UptimeRobot) pointed at `/health`, entirely outside this repo.
