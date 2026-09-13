# Demo Realism & Matching Engine Uplift — Design Spec

**Date:** 2026-09-13
**Status:** Approved by Phil (chat, 2026-09-13) — proceeding to implementation plan.
**Tracked as:** new **Workstream 9** in `CAPLink-Technical-Implementation-Plan.docx` /
`CAPLink-Technical-Tracker.xlsx`, following the existing Workstream → Epic → Step
convention (effort S/M/L, priority P0/P1/P2).

## 1. Motivation

Phil wants the CAPLink demo to behave like a real, populated platform rather than
the current one-of-everything seed (`scripts/seed_demo_data.py`: 1 university, 1
student, 1 business, 1 project). Four related asks:

1. Seed the database with realistic synthetic data (universities, courses,
   students with varied skills/degrees, businesses).
2. A real end-to-end demo: log in as a business, post a project, see plausible,
   well-differentiated matching students.
3. Use that synthetic data to make the matching engine's mathematics genuinely
   more sophisticated — not just a bigger seed script.
4. Explain the matching engine on the public `how-it-works.html` page, under a
   subheading that's technical but light-hearted.

Phil explicitly invited scoping this as its own tracked workstream rather than
untracked ad hoc work.

## 2. Relationship to the existing plan — resolving the Workstream 4 tension

The Technical Implementation Plan's **Workstream 4** (embeddings, pgvector, a
blended ranker) was deliberately deprioritized project-wide (see top-level
`CLAUDE.md`, "Deliberate scope decisions on Workstreams 4 and 6"): it needs real
hire/reject **outcome** data to train or validate a ranking model against, and
with zero real students/businesses on the platform, building it would mean
calibrating against synthetic outcomes and calling it validated — premature
infrastructure, not progress. That reasoning is still correct and **this spec
does not reopen it.**

What this spec actually does is a different, narrower thing: replace one
similarity *measurement* (bag-of-words/TF-IDF cosine similarity between a
project brief and a student's declared background) with a better similarity
measurement (semantic sentence embeddings). This needs no outcome data at
all — it only needs the text itself, which synthetic profiles/projects provide
just as validly as real ones would. No weights are being *learned* from
outcomes; the existing hand-tuned, explainable `MatchWeights` in
`app/services/matching/config.py` are untouched. This is explicitly **not**
Workstream 4 — it's an upgrade to one input feature, not a new ranking model.

**Non-goal:** nothing here trains, learns, or calibrates against outcome data,
real or synthetic. If that ever changes, it should be scoped as a Workstream 4
revival with its own explicit sign-off, not folded into this workstream quietly.

## 3. Scope decomposition — Workstream 9

| Step | Epic | Description | Effort | Priority |
|---|---|---|---|---|
| 9.a.i | Synthetic Data Generation | Design the synthetic dataset shape: universities/courses, a skills vocabulary aligned with `SKILL_SYNONYMS` and `CATEGORY_KEYWORDS`, business sectors/project types | S | P1 |
| 9.a.ii | Synthetic Data Generation | Generate ~60-100 diverse student profiles, ~15-20 businesses, ~20-30 projects across 3-4 universities/~15-20 courses | M | P1 |
| 9.a.iii | Synthetic Data Generation | Curate one "hero" demo business account: a compelling project brief and a clearly differentiated match spread (~90%+ top match tapering to a weak one) | S | P1 |
| 9.a.iv | Synthetic Data Generation | Wire the expanded dataset into an idempotent seed path (reset-and-reseed safely, repeatable before a pitch) | S | P1 |
| 9.b.i | Matching Engine Uplift | Add `sentence-transformers` (`all-MiniLM-L6-v2`) as a new gated dependency; a thin wrapper module with graceful fallback if the model/package isn't installed | S | P1 |
| 9.b.ii | Matching Engine Uplift | Precompute + cache embeddings on student/project save (new nullable DB columns + Alembic migration); backfill for the synthetic dataset | M | P1 |
| 9.b.iii | Matching Engine Uplift | Swap `text_similarity`'s scoring internals for embedding cosine similarity behind the existing factor contract; keep `scorer.py`'s explainability/renormalization untouched | M | P1 |
| 9.b.iv | Matching Engine Uplift | Test coverage: unit tests for the embedding wrapper and swapped factor (including the no-model-available fallback path), plus a sanity check against synthetic data that scores are sensibly differentiated | M | P1 |
| 9.c.i | Demo Verification | Real browser click-through (claude-in-chrome): login as the hero business, post/select the curated project, view the ranked matches end-to-end | S | P1 |
| 9.c.ii | Demo Verification | Document the reset/reseed workflow (how to wipe and repopulate before a live pitch) | S | P2 |
| 9.d.i | Marketing | Write and publish "The Secret Sauce (It's Just Maths)" subsection on `how-it-works.html` | S | P1 |

11 steps total. Priorities are P1 (important, not literally launch-blocking in
the existing P0 safeguarding/compliance sense) except the reset-workflow
documentation step, which is P2 polish.

## 4. Architecture — matching engine

**Model choice:** `sentence-transformers`'s `all-MiniLM-L6-v2` — ~80MB, CPU-only
inference, no API key, no network dependency at runtime once downloaded. This is
a deliberate, documented deviation from `text_similarity.py`'s own stated design
goal ("Deliberately not pulling in scikit-learn/numpy... a small dependency-free
implementation") — accepted knowingly here because Phil specifically asked for
more sophisticated mathematics, understanding the dependency-weight trade-off
(pulls in PyTorch; first install/deploy will be noticeably heavier).

**Caching, not per-request inference:** embeddings are computed once, at
student-profile save and at project save/update, and cached as a new column
(`embedding: JSON` — a plain list of ~384 floats; no pgvector, no ANN index —
at a few hundred rows, a brute-force NumPy dot product across all candidates is
sub-millisecond). Scoring reads the cached vectors; the model itself only needs
to be loaded into memory when a profile/project is actually written, not on
every feed/shortlist read. This keeps the API's steady-state request path exactly
as fast as it is today.

**Contract preserved:** `text_similarity.cosine_similarity(text_a, text_b, idf)`
today returns a float 0-1 from tokenized bag-of-words vectors. The swapped
version will still expose a same-shaped call (or an equivalent new function
`embedding_similarity(student, project)` called from `scorer.py` in the same
slot) returning a float 0-1, so `scorer.py`'s `ScoreFactor` construction,
dynamic renormalization, and reason-chip logic need zero changes. If a
student/project has no cached embedding yet (model unavailable at save time,
or a pre-existing row from before this migration), the factor falls back to
today's TF-IDF cosine similarity rather than being silently zeroed or crashing
— the same "graceful degradation" principle `scorer.py` already documents for
the collaborative-filtering factor.

**Not touched:** `skills.py`'s synonym+fuzzy skill-overlap matching stays
exactly as-is. It's already good and crisply explainable ("Matched skills:
python, sql"); embeddings go specifically where bag-of-words genuinely falls
short (free-text project brief vs. a student's prose-ish background), not
where a curated synonym table already does the job better and more legibly.

**Dependency gating:** follows the existing `requirements-integrations.txt` /
`requirements-postgres.txt` pattern — a new `requirements-ml.txt` (or similar)
holding `sentence-transformers`, kept out of the default `requirements.txt` the
same way Firebase is, since it's a large, wheel-heavier install not everyone
running this repo needs.

## 5. Synthetic data generation

- **Scale:** 3-4 universities, ~15-20 courses/degree titles (drawn from
  `CATEGORY_KEYWORDS`'s existing discipline vocabulary so degree-relevance
  scoring lines up naturally), ~60-100 students, ~15-20 businesses, ~20-30
  projects.
- **Realism:** skills drawn from a vocabulary that overlaps
  `SKILL_SYNONYMS` (so synonym/fuzzy matching has real work to do), varied
  degree titles across "strong" and "supporting" category keywords (so degree
  relevance scores are genuinely differentiated, not uniform), varied
  reputation histories (some students with strong completed-project track
  records, some brand new) so the Bayesian-shrunk reputation factor shows
  visible variation.
- **Hero account:** one specific, named business with a well-written project
  brief and a curated set of candidate students engineered (via their skills/
  degree/text) to produce a clear best-to-weakest match story — this is the
  account used for live demos/pitches.
- **Where it lives:** extends the existing `scripts/seed_demo_data.py` pattern
  (idempotent, safe to rerun) rather than introducing a second, divergent
  seeding mechanism.

## 6. Demo verification (9.c)

A real browser click-through via `claude-in-chrome`, matching this project's
established practice of verifying frontend/flow changes live rather than by
inspection alone: log in as the hero business account, post (or select the
pre-seeded) project, and confirm the ranked match list renders with the
expected differentiated scores and explanations. Verified against `/app`
directly (the reference UI), not just via `TestClient`.

## 7. Marketing page content (9.d)

`docs/how-it-works.html` currently has a "How matching works" section (around
its final `<section>`) whose copy explicitly says *"The detail of how that
scoring works stays internal."* This spec adds a new subsection under the
heading **"The Secret Sauce (It's Just Maths)"** — plain-English, mildly funny
walk-through of the six scoring factors (skills, semantic fit, degree
relevance, rate/availability, reputation, collaborative signal) — while
**keeping exact weights/thresholds and the literal scoring formula
unpublished**, for the same reason a credit-scoring or spam-filter algorithm
doesn't publish its exact coefficients: it invites gaming. The existing
"stays internal" sentence gets softened/reworded so it doesn't flatly
contradict a subsection that now explains the general mechanism — something
like acknowledging we're happy to explain *how* it thinks without handing out
the exact recipe. Matches the existing site's design tokens, tone, and
no-build-step convention (same as the rest of `docs/*.html`).

## 8. Testing

- Unit tests for the embedding wrapper module (mocked/small-scale, not
  re-testing sentence-transformers itself) including the no-model-available
  fallback path.
- Unit tests for the swapped `text_similarity`/scorer factor confirming scores
  are still 0-1, still explainable, and behave sensibly on a few hand-picked
  text pairs (near-duplicate text scores high, unrelated text scores low).
- A sanity script/test run against the synthetic dataset confirming matches
  are meaningfully differentiated (not everyone scoring ~the same), especially
  for the hero account's project.
- Existing matching-engine test suite must continue to pass unchanged (the
  factor contract isn't changing shape, only its internals).

## 9. Risks / open items to flag, not block on

- **Deploy weight:** `sentence-transformers` + PyTorch is the heaviest
  dependency this repo will have pulled in. First Render deploy after this
  lands will be slower to build and larger; worth watching build/memory
  headroom on whatever Render tier is in use, though not a blocker for local/
  demo purposes.
- **Model download at first use:** the model itself (~80MB) downloads on
  first load unless vendored/cached ahead of time — fine for a dev machine
  with internet access, worth a documented note for anyone cloning fresh
  (mirrors the existing dad's-machine troubleshooting pattern in
  `caplink/CLAUDE.md` — flag, don't silently assume connectivity).
- **Public-page honesty:** the marketing copy must not overclaim ("AI-powered"
  buzzword framing) given the actual mechanism is explainable rules plus one
  semantic-similarity factor, not a black-box model — keep the tone accurate,
  not just funny.
