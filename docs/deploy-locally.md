# Running the full local app (`/app`)

This is for the project owner — a working-technical-knowledge walkthrough of
the fuller reference frontend, distinct from:

- [README.md](../README.md)'s Quickstart — installing Python/venv/dependencies
  in the first place.
- [very simple explanation for very simple man (dadster).md](<very simple explanation for very simple man (dadster).md>)
  — a from-scratch, zero-jargon guide for someone who's never touched a
  programming tool, aimed at `/demo`.

If you haven't got the backend installed yet, go do that first
([02-getting-started.md](02-getting-started.md)), then come back here.

## Start the backend

```bash
uvicorn app.main:app --reload
```

On first run against an empty database, this auto-seeds a demo university
(Manchester), student (Aisha Rahman), business (DataCraft Analytics), and one
open project — see `scripts/seed_demo_data.py`. This only happens once: it
checks whether any `University` row exists before seeding, so restarting the
server won't reseed or duplicate anything. If you want a genuinely fresh
database, stop the server, delete `caplink.db`, and start it again.

## Where things live

| Path | What it is |
|---|---|
| `/docs` | Swagger UI — every endpoint, try-it-out included |
| `/demo` | The lightweight teaser (`static/demo/`) — a handful of flows, some now fixed by this same work (see below) |
| `/app` | **This app** (`static/app/`) — nearly the entire API, all three roles |

Login credentials (same for all three, seeded by `scripts/seed_demo_data.py`):

| Role | Email | Password |
|---|---|---|
| Student | `aisha.rahman@manchester.ac.uk` | `ChangeMe123!` |
| Business | `hello@datacraft-analytics.com` | `ChangeMe123!` |
| University admin | `admin@manchester.ac.uk` | `ChangeMe123!` |

`/app`'s login screen has one-click buttons for all three — no need to type
these in by hand.

## Walkthrough

### Student

1. **Feed tab** — your profile, then the ranked project feed (match score +
   plain-English reasons), apply to one with a cover note. Career
   suggestions render underneath, driven by your listed skills.
2. **Contracts tab** — empty until a business hires you from an
   application (see the Business section below). Once one exists: submit a
   milestone when it's `pending`, accept IP/NDA terms, message the business,
   or rate the contract.
3. **Messages tab** — conversations you're part of. Threads only ever start
   from a contract or applicant card ("Message X") — there's no generic
   "compose to anyone" box, since a message thread always needs a real
   counterpart relationship behind it.
4. **Local Search tab** — degree-relevant businesses within N miles of your
   campus. Works immediately for the seeded account (Manchester + DataCraft
   are both pre-geocoded in the seed script) — you'll see DataCraft Analytics
   show up at ~1 mile. If you ever see "campus location hasn't been set yet"
   here, that means the university's admin hasn't set a postcode (see below)
   — it's an expected state for a *newly registered* university, not a bug.
5. **My Ratings tab** — your rating history, both directions. A rating you
   *received* stays hidden (no score shown) until the other side rates you
   too — this is the platform's blind-until-both-submit rule, not a loading
   bug.

### Business

1. **My Projects tab** — profile (set a postcode here to become eligible for
   student local-search results), request access to a university (starts
   `pending` until an admin approves it — try posting a project before
   approval to see the safeguarding rejection message), post a project, view
   your projects and their real applicants (message them, update application
   status, or create a contract).
2. **Contracts tab** — same view as the student side, mirrored: approve &
   pay a milestone once it's `submitted`, accept terms, message, rate.
3. **Messages tab** — same as the student side.

### University admin

1. **Partnerships tab** — every business agreement request for your
   university. Expand "Manage this agreement" to approve/reject/suspend and
   pick exactly which student bands and project categories that business can
   access — this is the core safeguarding control.
2. **Campus Location tab** — set/update the campus postcode. This is what
   the student-side local search measures distance from, and needs live
   internet access (it geocodes via [postcodes.io](https://postcodes.io)
   server-side). The seeded university already has one set, so you'll only
   see this matter in practice for a university you register/onboard fresh.

### Messaging's off-platform-contact flag

From any contract or applicant card, start a conversation and send an
ordinary message, then send one like *"let's just pay you directly, call me
on 07911123456"* — it'll show with a flagged badge and reason on the
recipient's side. This is the same safeguarding check described in
[03-user-guide-demo-walkthrough.md](03-user-guide-demo-walkthrough.md)'s
curl-based version, just clickable here instead.

## What was actually missing before this existed

The backend didn't have "list" endpoints for a few things a real UI needs —
your own projects, real applicants (as opposed to ranked candidates), your
contracts, your message threads, your rating history. These now exist
(`GET /projects/mine`, `GET /projects/{id}/applications`, `GET
/contracts/mine`, `GET /messages/threads`, `GET /ratings/mine`) — see
`CLAUDE.md` for the full list if you're extending this further. `/demo`'s
"My projects" / "View applicants" panels, which called two of these same
paths and 404'd before, now work unmodified as a side effect.
