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
