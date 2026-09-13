# Demo Realism & Matching Engine Uplift Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the CAPLink demo feel like a real, populated platform — realistic synthetic universities/students/businesses/projects, a genuinely more sophisticated (semantic-embedding-powered) matching engine, a repeatable "login as a business, post a project, see differentiated matches" demo, and a public explanation of how matching works.

**Architecture:** Add a local sentence-embedding model as a cached, optional signal inside the existing rules-based matching engine (swap-in replacement for one factor's internals, not a new ranking model). Rewrite `scripts/seed_demo_data.py` to generate a small, varied synthetic dataset via a deterministic generator plus one hand-crafted "hero" demo account. Verify end-to-end via both a new HTTP-level pytest and a real browser click-through. Publish a plain-English, lightly funny explanation of the six scoring factors on the marketing site.

**Tech Stack:** FastAPI / SQLAlchemy / Alembic / pytest (existing stack). New: `sentence-transformers` (CPU-only, `all-MiniLM-L6-v2`) in a new gated `requirements-ml.txt`, following the existing `requirements-integrations.txt` pattern.

**Spec:** `caplink/docs/superpowers/specs/2026-09-13-demo-realism-matching-uplift-design.md`

## Global Constraints

- `sentence-transformers` (and its PyTorch dependency) goes in a new `requirements-ml.txt`, never in `requirements.txt` — this repo's existing convention (see `requirements-integrations.txt`'s header) keeps heavy/optional installs opt-in.
- No pgvector, no vector index, no new infra — embeddings are plain JSON float lists on existing rows; cosine similarity is a Python dot product. This dataset is small (~100 rows), so brute-force is correct and simpler.
- Every embedding-aware code path must degrade gracefully to today's TF-IDF behavior when `sentence-transformers` isn't installed or a row has no cached embedding yet — never raise, never silently score 0.
- This work does **not** train, learn, or calibrate anything against outcome data (real or synthetic) — see spec §2. If a task here starts to feel like it's building a ranking model, stop; that's out of scope (Workstream 4).
- Match this repo's existing per-module test-file convention (`tests/test_<module>.py` for pure unit tests, `tests/test_<feature>_e2e.py` for real-HTTP tests via the `client` fixture in `tests/conftest.py`).
- The marketing page edit must not overclaim ("AI-powered" buzzword framing) — the mechanism is explainable rules plus one semantic-similarity factor, and the copy should say so honestly while staying light-hearted.
- Commit after every task (see each task's final step). Never batch multiple tasks into one commit.

---

## Task 1: Embeddings module (with graceful no-model fallback)

**Files:**
- Create: `app/services/matching/embeddings.py`
- Create: `requirements-ml.txt`
- Test: `tests/test_embeddings.py`

**Interfaces:**
- Produces: `embeddings.is_available() -> bool`, `embeddings.embed_text(text: str) -> Optional[list[float]]`, `embeddings.cosine_similarity_vectors(a: list[float], b: list[float]) -> float`, `embeddings.embedding_similarity_score(a: list[float], b: list[float]) -> float` (0-1, clamps negative cosine to 0), `embeddings.student_corpus_text(student) -> str`, `embeddings.project_corpus_text(project) -> str` — all consumed by Task 3 and Task 4.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_embeddings.py
from app.services.matching import embeddings


def test_embed_text_returns_none_for_empty_text():
    assert embeddings.embed_text("") is None
    assert embeddings.embed_text("   ") is None


def test_embed_text_returns_a_vector_when_model_available():
    if not embeddings.is_available():
        return  # sentence-transformers not installed in this environment — nothing to assert
    vector = embeddings.embed_text("Analyse customer churn using Python and SQL")
    assert vector is not None
    assert len(vector) > 0
    assert all(isinstance(v, float) for v in vector)


def test_similar_sentences_score_higher_than_unrelated_ones():
    if not embeddings.is_available():
        return
    a = embeddings.embed_text("Build an interactive dashboard to visualise customer retention data")
    b = embeddings.embed_text("Create a dashboard showing customer churn and retention trends")
    c = embeddings.embed_text("Design a brand refresh and new logo for a coffee shop")
    assert embeddings.embedding_similarity_score(a, b) > embeddings.embedding_similarity_score(a, c)


def test_cosine_similarity_vectors_handles_mismatched_or_empty_input():
    assert embeddings.cosine_similarity_vectors([], [1.0]) == 0.0
    assert embeddings.cosine_similarity_vectors([1.0, 0.0], [1.0]) == 0.0


def test_embedding_similarity_score_clamps_negative_cosine_to_zero():
    assert embeddings.embedding_similarity_score([1.0, 0.0], [-1.0, 0.0]) == 0.0


def test_student_corpus_text_joins_skills_modules_and_degree():
    class _FakeStudent:
        skills = ["Python", "SQL"]
        modules = ["Statistics II"]
        degree_title = "BSc Data Science"

    text = embeddings.student_corpus_text(_FakeStudent())
    assert text == "Python SQL Statistics II BSc Data Science"


def test_project_corpus_text_joins_title_description_and_required_skills():
    class _FakeProject:
        title = "Churn Analysis"
        description = "Find the top churn drivers."
        required_skills = ["Python", "SQL"]

    text = embeddings.project_corpus_text(_FakeProject())
    assert text == "Churn Analysis Find the top churn drivers. Python SQL"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_embeddings.py -v`
Expected: FAIL with `ModuleNotFoundError` / `AttributeError: module 'app.services.matching.embeddings' has no attribute ...` (the module doesn't exist yet).

- [ ] **Step 3: Create `requirements-ml.txt`**

```
# Optional, heavy dependency for the matching engine's semantic-similarity
# factor (app/services/matching/embeddings.py) — pulls in PyTorch, by far
# the largest install this repo has. Kept out of requirements.txt the same
# way requirements-integrations.txt keeps firebase-admin out: every
# embedding-aware code path degrades gracefully to the original TF-IDF
# text-similarity behaviour when this isn't installed, so it's genuinely
# optional, not a silent requirement.
#
# Install with: pip install -r requirements.txt -r requirements-ml.txt
sentence-transformers>=3.0.0
```

- [ ] **Step 4: Install the dependency locally**

Run: `pip install -r requirements-ml.txt`
Expected: installs `sentence-transformers` and `torch` (this will take a few minutes and ~1-2GB of disk the first time — expected, not an error).

- [ ] **Step 5: Write the implementation**

```python
# app/services/matching/embeddings.py
"""
Semantic sentence embeddings for the matching engine's text-similarity
factor.

A local, offline model (no API key, no network at runtime beyond the
one-time model download on first use) — computed once when a student
profile or project is created/updated and cached on the row
(StudentProfile.embedding / Project.embedding), never recomputed on a
normal read like a feed or shortlist request.

Deliberately optional: `sentence-transformers` lives in requirements-ml.txt,
not requirements.txt, since it pulls in PyTorch — a much heavier install
than anything else this project depends on (see that file's header).
Every function here degrades to `None`/`0.0` rather than raising if the
package isn't installed or the model can't load — app/services/matching/
scorer.py falls back to the original TF-IDF text_similarity factor
whenever that happens. This module is never a hard requirement to run
the app.
"""
from functools import lru_cache
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from app.models.project import Project
    from app.models.user import StudentProfile

EMBEDDING_MODEL_NAME = "all-MiniLM-L6-v2"


@lru_cache(maxsize=1)
def _load_model():
    """Lazily loads and caches the sentence-transformers model. Returns
    None (not an exception) if the package isn't installed — the one
    place this module treats that as an expected, valid state rather
    than an error."""
    try:
        from sentence_transformers import SentenceTransformer
    except ImportError:
        return None
    return SentenceTransformer(EMBEDDING_MODEL_NAME)


def is_available() -> bool:
    return _load_model() is not None


def embed_text(text: str) -> Optional[list[float]]:
    """Returns a unit-normalized embedding vector for `text`, or None if
    the model isn't available or the text is empty/whitespace-only."""
    if not text or not text.strip():
        return None
    model = _load_model()
    if model is None:
        return None
    vector = model.encode(text, normalize_embeddings=True)
    return vector.tolist()


def cosine_similarity_vectors(vec_a: list[float], vec_b: list[float]) -> float:
    """Both vectors are already unit-normalized by embed_text, so cosine
    similarity is just their dot product. Still guards defensively against
    empty or mismatched-length input (e.g. a stale cached vector from a
    future model swap with a different dimension)."""
    if not vec_a or not vec_b or len(vec_a) != len(vec_b):
        return 0.0
    dot = sum(a * b for a, b in zip(vec_a, vec_b))
    return max(-1.0, min(1.0, dot))  # clamp floating-point drift outside [-1, 1]


def embedding_similarity_score(vec_a: list[float], vec_b: list[float]) -> float:
    """Maps cosine similarity to this engine's 0-1 raw-score convention.
    Negative cosine (near-opposite meaning) clamps to 0 rather than being
    treated as a large negative signal — every other factor in this engine
    is 0-1, and a negative contribution would break the dynamic
    renormalization in scorer.py."""
    return max(0.0, cosine_similarity_vectors(vec_a, vec_b))


def student_corpus_text(student: "StudentProfile") -> str:
    return " ".join([*student.skills, *student.modules, student.degree_title])


def project_corpus_text(project: "Project") -> str:
    return " ".join([project.title, project.description, *project.required_skills])


def refresh_student_embedding(student: "StudentProfile") -> None:
    """Recomputes and sets `student.embedding` from the student's current
    skills/modules/degree title. Call this any time those fields change —
    registration, SSO JIT provisioning, or a profile update — before the
    session commits. Sets embedding to None (never a stale vector) if the
    model isn't available or the student's corpus text is empty."""
    student.embedding = embed_text(student_corpus_text(student))


def refresh_project_embedding(project: "Project") -> None:
    """Same idea as refresh_student_embedding, for a project's title/
    description/required_skills. Call right after constructing a Project,
    before it's committed."""
    project.embedding = embed_text(project_corpus_text(project))
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `pytest tests/test_embeddings.py -v`
Expected: PASS (all 7 tests — the model-dependent ones actually exercise the real model since Step 4 installed it).

- [ ] **Step 7: Commit**

```bash
git add app/services/matching/embeddings.py requirements-ml.txt tests/test_embeddings.py
git commit -m "$(cat <<'EOF'
Add optional semantic-embedding module for the matching engine (Workstream 9.b.i)

Local, offline sentence-transformers model (all-MiniLM-L6-v2), gated
behind a new requirements-ml.txt so it stays fully optional. Every
function degrades gracefully to None/0.0 when the package isn't
installed — nothing here is a hard dependency yet, it's wired into
scoring in a later task.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

---

## Task 2: Cache embeddings on StudentProfile and Project (migration)

**Files:**
- Modify: `app/models/user.py` (StudentProfile class)
- Modify: `app/models/project.py` (Project class)
- Create: `alembic/versions/<autogenerated>_add_embedding_columns.py`
- Test: `tests/test_embeddings.py` (extend)

**Interfaces:**
- Produces: `StudentProfile.embedding: Optional[list[float]]`, `Project.embedding: Optional[list[float]]` — both nullable JSON columns, consumed by Task 3 (writers) and Task 4 (scorer.py reader).

- [ ] **Step 1: Write the failing test**

```python
# tests/test_embeddings.py — append
from app.models.enums import ProjectCategory, ProjectStatus, StudentBand
from app.models.project import Project
from app.models.user import StudentProfile


def test_student_profile_and_project_have_a_nullable_embedding_column():
    student = StudentProfile(
        user_id="u1", university_id="uni-1", degree_title="BSc Data Science", band=StudentBand.YEAR_3,
    )
    project = Project(
        business_id="biz-1", title="t", description="d", category=ProjectCategory.DATA_ANALYTICS,
        duration_label="1 week", hourly_rate_gbp=20, status=ProjectStatus.OPEN,
    )
    assert student.embedding is None
    assert project.embedding is None
    student.embedding = [0.1, 0.2]
    project.embedding = [0.3, 0.4]
    assert student.embedding == [0.1, 0.2]
    assert project.embedding == [0.3, 0.4]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_embeddings.py::test_student_profile_and_project_have_a_nullable_embedding_column -v`
Expected: FAIL — `TypeError: 'embedding' is an invalid keyword argument` or `AttributeError` (the column doesn't exist yet).

- [ ] **Step 3: Add the columns to both models**

In `app/models/user.py`, inside `class StudentProfile`, add near the other JSON columns (after `portfolio_urls`):

```python
    # Technical Implementation Plan 9.b.ii — cached semantic embedding of
    # this student's skills/modules/degree (see
    # app/services/matching/embeddings.py). Nullable: None means "not yet
    # computed" (sentence-transformers unavailable at save time, or a row
    # predating this column) — scorer.py falls back to TF-IDF text
    # similarity whenever it's None, never crashes or treats it as zero.
    embedding: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
```

In `app/models/project.py`, inside `class Project`, add near `required_skills`:

```python
    # Technical Implementation Plan 9.b.ii — see StudentProfile.embedding's
    # comment in app/models/user.py; same idea, same fallback behaviour.
    embedding: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
```

`Optional` and `JSON` are already imported in both files (check the top of each — `user.py` imports `JSON` and `Optional` already for other fields; `project.py` imports `JSON` already for `required_skills`/`target_university_ids`, confirm `Optional` is imported too and add it to the existing `typing` import line if not).

- [ ] **Step 4: Generate and inspect the migration**

Run: `alembic revision --autogenerate -m "add embedding columns to student_profiles and projects"`

Open the generated file in `alembic/versions/`. It should contain exactly two `op.add_column` calls (one per table, both `sa.Column('embedding', sa.JSON(), nullable=True)`) in `upgrade()`, and two matching `op.drop_column` calls in `downgrade()`. If autogenerate also produced an `alter_column` touching an unrelated enum column (e.g. `milestones.status`), remove it — this is the same SQLite-enum-as-VARCHAR false positive already documented in `alembic/versions/c9fc3db88d6f_add_data_protection_fields_last_login_.py`, not a real change.

- [ ] **Step 5: Apply the migration and run tests**

Run: `alembic upgrade head`
Run: `pytest tests/test_embeddings.py -v`
Expected: PASS (all tests, including the new one).

- [ ] **Step 6: Commit**

```bash
git add app/models/user.py app/models/project.py alembic/versions/ tests/test_embeddings.py
git commit -m "$(cat <<'EOF'
Add cached embedding columns to StudentProfile and Project (Workstream 9.b.ii)

Nullable JSON columns holding a precomputed semantic-embedding vector.
Deliberately not pgvector/an ANN index — at this dataset's scale a
brute-force dot product at scoring time is simpler and fast enough.
Null means "not yet computed"; the scorer falls back to TF-IDF rather
than treating a missing embedding as a mismatch.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

---

## Task 3: Wire embedding refresh into every write path

**Files:**
- Modify: `app/api/v1/endpoints/auth.py`
- Modify: `app/api/v1/endpoints/saml.py`
- Modify: `app/api/v1/endpoints/students.py`
- Modify: `app/api/v1/endpoints/projects.py`
- Modify: `app/services/matching/__init__.py`
- Test: `tests/test_embeddings_write_paths_e2e.py`

**Interfaces:**
- Consumes: `embeddings.refresh_student_embedding`, `embeddings.refresh_project_embedding` from Task 1.
- Produces: `matching.refresh_student_embedding`, `matching.refresh_project_embedding` (re-exported from the package's public `__init__.py`, per this module's own "only import from here" contract) — consumed by every call site below and by Task 9's seed script.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_embeddings_write_paths_e2e.py
"""Workstream 9.b.ii/iii — every real write path that creates or edits a
student profile or a project must end up with a cached `embedding` (when
sentence-transformers is installed) so the matching engine's semantic
factor actually has something to read. This test skips its assertions
(rather than failing) when the model isn't installed in this environment,
matching tests/test_embeddings.py's existing pattern."""
from app.models.enums import ProjectCategory, StudentBand
from app.models.project import Project
from app.models.user import StudentProfile
from app.services.matching import embeddings

from tests.test_golden_path_e2e import _auth, _register_business, _register_student, _seed_university
from tests.test_applications_e2e import _approve_agreement, _post_project


def test_student_registration_populates_embedding(client, db_session_factory):
    if not embeddings.is_available():
        return
    university_id = _seed_university(client, slug="embeduni", domain="embeduni.ac.uk")
    _register_student(client, university_slug="embeduni", email="embed-student@embeduni.ac.uk")

    db = db_session_factory()
    student = db.query(StudentProfile).filter(StudentProfile.university_id == university_id).first()
    assert student is not None
    assert student.embedding is not None
    assert len(student.embedding) > 0
    db.close()


def test_profile_update_recomputes_embedding(client, db_session_factory):
    if not embeddings.is_available():
        return
    _seed_university(client, slug="embedupdateuni", domain="embedupdateuni.ac.uk")
    token = _register_student(client, university_slug="embedupdateuni", email="embed-update@embedupdateuni.ac.uk")

    resp = client.patch(
        "/api/v1/students/me", headers=_auth(token), json={"skills": ["Python", "SQL", "React"]},
    )
    assert resp.status_code == 200, resp.text

    db = db_session_factory()
    student = db.query(StudentProfile).filter(StudentProfile.user_id.isnot(None)).order_by(StudentProfile.created_at.desc()).first()
    assert student.skills == ["Python", "SQL", "React"]
    assert student.embedding is not None
    db.close()


def test_project_creation_populates_embedding(client, db_session_factory):
    if not embeddings.is_available():
        return
    university_id = _seed_university(client, slug="embedprojuni", domain="embedprojuni.ac.uk")
    business_token = _register_business(client, email="embed-project-business@example.com")
    _approve_agreement(
        client, business_user_email="embed-project-business@example.com", university_id=university_id,
        bands=[StudentBand.YEAR_3.value], categories=[ProjectCategory.SOFTWARE_ENGINEERING.value],
    )
    project = _post_project(client, business_token=business_token, university_id=university_id)

    db = db_session_factory()
    row = db.query(Project).filter(Project.id == project["id"]).first()
    assert row.embedding is not None
    assert len(row.embedding) > 0
    db.close()
```

This test needs a `db_session_factory` fixture that hands back the *same* isolated engine the `client` fixture uses, so the test can query rows the request created. Add it to `tests/conftest.py` right after the `client` fixture — read that fixture first to find the exact override/engine variable names it creates, and expose that same `sessionmaker` bound to that same engine as a new fixture:

```python
@pytest.fixture()
def db_session_factory(client):
    """Exposes the same isolated engine/session the `client` fixture just
    set up (via its get_db override), so a test can query rows created
    through real HTTP requests. Depends on `client` so the override is
    already in place before this fixture's caller uses it."""
    from app.db.session import SessionLocal
    return SessionLocal
```

Adjust the import/binding above once you've actually read `tests/conftest.py`'s `client` fixture — if it overrides `app.db.session.SessionLocal`/`engine` directly (rather than only overriding the `get_db` dependency callable), return that same overridden `SessionLocal`; if it only patches the FastAPI dependency, instead capture and expose the local `SessionLocal` object the fixture builds internally. Whichever it is, the goal is one line: a fixture returning a callable that opens a new session against the exact database the test's HTTP requests just wrote to.

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_embeddings_write_paths_e2e.py -v`
Expected: FAIL — `student.embedding` / `row.embedding` is `None` (nothing calls `refresh_*_embedding` yet), or a fixture error if `db_session_factory` needs adjusting per Step 1's note.

- [ ] **Step 3: Export the two functions from the matching package**

Modify `app/services/matching/__init__.py`:

```python
from app.services.matching.config import ALGORITHM_VERSION, DEFAULT_WEIGHTS, MatchWeights
from app.services.matching.embeddings import refresh_project_embedding, refresh_student_embedding
from app.services.matching.scorer import (
    MatchResult,
    ScoreFactor,
    rank_projects_for_student,
    rank_students_for_project,
    score_student_against_project,
)

__all__ = [
    "ALGORITHM_VERSION",
    "DEFAULT_WEIGHTS",
    "MatchWeights",
    "MatchResult",
    "ScoreFactor",
    "rank_projects_for_student",
    "rank_students_for_project",
    "score_student_against_project",
    "refresh_project_embedding",
    "refresh_student_embedding",
]
```

- [ ] **Step 4: Wire the student registration endpoint**

In `app/api/v1/endpoints/auth.py`, add `from app.services import matching` to the imports (alongside the other `from app.services...` lines), then update the registration handler:

```python
    profile = StudentProfile(
        user_id=user.id,
        university_id=university.id,
        degree_title=payload.degree_title,
        band=payload.band,
        data_sharing_consent_at=datetime.utcnow(),
    )
    matching.refresh_student_embedding(profile)
    db.add(profile)
```

(`refresh_student_embedding` reads `profile.skills`/`profile.modules`/`profile.degree_title` — `skills`/`modules` default to `[]` per the model, so this is safe even though registration doesn't collect them yet; the embedding will just be based on the degree title alone until a profile update adds skills.)

- [ ] **Step 5: Wire the SAML JIT-provisioning path**

In `app/api/v1/endpoints/saml.py`, add `from app.services import matching` to the imports, then change the inline `db.add(StudentProfile(...))` to assign first so it can be passed to `refresh_student_embedding`:

```python
        band = mapped["band"] if mapped["band"] in {b.value for b in StudentBand} else saml_service.DEFAULT_JIT_BAND
        jit_profile = StudentProfile(
            user_id=user.id,
            university_id=university.id,
            degree_title=mapped["degree_title"] or saml_service.PLACEHOLDER_DEGREE_TITLE,
            band=band,
        )
        matching.refresh_student_embedding(jit_profile)
        db.add(jit_profile)
```

Keep every other field/comment in that block exactly as it already is (the `data_sharing_consent_at` comment above it stays put) — only the variable assignment and the new `matching.refresh_student_embedding(jit_profile)` call are new.

- [ ] **Step 6: Wire the student profile update endpoint**

In `app/api/v1/endpoints/students.py`, add `from app.services import matching` to the imports, then update `update_my_profile`:

```python
@router.patch("/me", response_model=StudentProfileOut)
def update_my_profile(
    payload: StudentProfileUpdate, db: Session = Depends(get_db), user: User = Depends(require_student)
):
    """Partial update — skills, rate expectation, weekly availability.
    Changing any of these changes future match scores, not past ones."""
    profile = _get_own_profile(db, user)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(profile, field, value)
    # Unconditional, not just when skills/modules/degree_title changed —
    # recomputing on every update is cheap relative to the update itself
    # and avoids tracking which specific fields are embedding-relevant.
    matching.refresh_student_embedding(profile)
    db.commit()
    db.refresh(profile)
    return profile
```

- [ ] **Step 7: Wire the project creation endpoint**

In `app/api/v1/endpoints/projects.py` (already imports `matching`), update `create_project`:

```python
    project = Project(
        business_id=business.id,
        title=payload.title,
        description=payload.description,
        category=payload.category,
        required_skills=payload.required_skills,
        duration_label=payload.duration_label,
        estimated_hours=payload.estimated_hours,
        hourly_rate_gbp=payload.hourly_rate_gbp,
        is_remote=payload.is_remote,
        location_label=payload.location_label,
        target_university_ids=payload.target_university_ids,
        target_bands=[b.value for b in payload.target_bands],
        status=ProjectStatus.PENDING_REVIEW if needs_review else ProjectStatus.OPEN,
    )
    matching.refresh_project_embedding(project)
    db.add(project)
```

- [ ] **Step 8: Run tests to verify they pass**

Run: `pytest tests/test_embeddings_write_paths_e2e.py -v`
Expected: PASS (all 3 tests, assuming `sentence-transformers` is installed in this environment — otherwise they short-circuit and trivially pass).

- [ ] **Step 9: Run the full existing test suite to check for regressions**

Run: `pytest -x -q`
Expected: PASS — every pre-existing test (registration, SAML, profile updates, project creation) still passes; this task only adds a side-effect, it doesn't change any response shape or status code.

- [ ] **Step 10: Commit**

```bash
git add app/api/v1/endpoints/auth.py app/api/v1/endpoints/saml.py app/api/v1/endpoints/students.py app/api/v1/endpoints/projects.py app/services/matching/__init__.py tests/test_embeddings_write_paths_e2e.py tests/conftest.py
git commit -m "$(cat <<'EOF'
Wire embedding refresh into every student/project write path (Workstream 9.b.ii)

Registration, SSO JIT provisioning, profile updates, and project
creation now all populate the new cached embedding column via
matching.refresh_student_embedding/refresh_project_embedding, so the
matching engine's semantic factor (next task) has real data to read
without any per-request model inference.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

---

## Task 4: Swap the text-similarity factor to prefer embeddings, with TF-IDF fallback

**Files:**
- Modify: `app/services/matching/scorer.py`
- Modify: `app/services/matching/config.py` (bump `ALGORITHM_VERSION`)
- Test: `tests/test_scorer.py` (extend)

**Interfaces:**
- Consumes: `embeddings.embedding_similarity_score`, `embeddings.student_corpus_text`, `embeddings.project_corpus_text` from Task 1.
- Produces: no change to `score_student_against_project`/`rank_students_for_project`/`rank_projects_for_student`'s signatures or `MatchResult`/`ScoreFactor` shape — only the `text_similarity` factor's internals and `ALGORITHM_VERSION`'s value change.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_scorer.py — append
from app.services.matching import embeddings


def test_text_similarity_uses_cached_embeddings_when_present():
    student = _make_student(skills=["Python"], modules=[], degree_title="BSc Data Science")
    project = _make_project(required_skills=["Python"])
    student.embedding = [1.0, 0.0]
    project.embedding = [1.0, 0.0]  # identical vector -> perfect embedding similarity

    result = score_student_against_project(student, project)
    text_factor = next(f for f in result.breakdown if f.name == "text_similarity")
    assert text_factor.raw_score == 1.0
    assert "semantic" in text_factor.detail.lower()


def test_text_similarity_falls_back_to_tfidf_when_no_embedding_cached():
    student = _make_student()  # embedding is None by default
    project = _make_project()  # embedding is None by default
    result = score_student_against_project(student, project)
    text_factor = next(f for f in result.breakdown if f.name == "text_similarity")
    assert "semantic" not in text_factor.detail.lower()
    assert 0.0 <= text_factor.raw_score <= 1.0


def test_text_similarity_falls_back_when_only_one_side_has_an_embedding():
    student = _make_student()
    student.embedding = [1.0, 0.0]
    project = _make_project()  # no embedding
    result = score_student_against_project(student, project)
    text_factor = next(f for f in result.breakdown if f.name == "text_similarity")
    assert "semantic" not in text_factor.detail.lower()  # partial data -> fall back, don't guess
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_scorer.py -v -k "embedding"`
Expected: FAIL — `text_factor.detail` never contains "semantic" yet (nothing reads `.embedding` in `scorer.py` today).

- [ ] **Step 3: Update `scorer.py`**

Replace the two private corpus-text functions and the text-similarity block:

```python
# Remove these two functions entirely (moved to embeddings.py in Task 1):
# def _student_corpus_text(student: StudentProfile) -> str: ...
# def _project_corpus_text(project: Project) -> str: ...
```

Add the import (alongside the existing `from app.services.matching import text_similarity` line):

```python
from app.services.matching import embeddings, text_similarity
```

Replace every call to `_student_corpus_text(...)` with `embeddings.student_corpus_text(...)`, and every call to `_project_corpus_text(...)` with `embeddings.project_corpus_text(...)` — there are three call sites total across `score_student_against_project`, `rank_projects_for_student`, and `rank_students_for_project` (the two IDF-corpus-building lines, plus the one inside the text-similarity block below).

Replace the "Free-text similarity" block inside `score_student_against_project`:

```python
    # --- Free-text similarity (project brief vs student's declared background) ---
    # Prefers cached semantic embeddings (Workstream 9.b) when BOTH sides
    # have one; falls back to the original TF-IDF cosine similarity
    # otherwise (model unavailable when either row was saved, or a row
    # predating this feature) — never a hard requirement, never a crash.
    if student.embedding and project.embedding:
        text_raw = embeddings.embedding_similarity_score(student.embedding, project.embedding)
        text_detail = (
            "Project brief closely matches student's background (semantic match)"
            if text_raw >= 0.35 else "Limited semantic overlap with student's background"
        )
    else:
        text_raw = text_similarity.cosine_similarity(
            embeddings.project_corpus_text(project), embeddings.student_corpus_text(student), idf
        )
        text_detail = (
            "Project brief closely matches student's background"
            if text_raw >= 0.35 else "Limited textual overlap"
        )
    factors.append(ScoreFactor("text_similarity", text_raw, weight_map["text_similarity"], 0.0, text_detail))
```

- [ ] **Step 4: Bump the algorithm version**

In `app/services/matching/config.py`:

```python
# Bumped from rules_v2 to hybrid_v3: the text_similarity factor now prefers
# a cached semantic-embedding score over TF-IDF cosine similarity whenever
# both sides of a comparison have one (Workstream 9.b) — every other
# factor and the overall weighting scheme is unchanged.
ALGORITHM_VERSION = "hybrid_v3"
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest tests/test_scorer.py tests/test_text_similarity.py -v`
Expected: PASS — all existing `test_scorer.py`/`test_text_similarity.py` tests plus the 3 new ones. (The existing tests never set `.embedding`, so they exercise the TF-IDF fallback path exactly as before — this confirms the swap is additive, not breaking.)

- [ ] **Step 6: Run the full test suite**

Run: `pytest -x -q`
Expected: PASS. If anything asserts `algorithm_version == "rules_v2"` literally, update that assertion to `"hybrid_v3"` (grep for `rules_v2` first: `grep -rn "rules_v2" tests/`).

- [ ] **Step 7: Commit**

```bash
git add app/services/matching/scorer.py app/services/matching/config.py tests/test_scorer.py
git commit -m "$(cat <<'EOF'
Swap text_similarity's internals for semantic embeddings, keep TF-IDF fallback (Workstream 9.b.iii)

score_student_against_project's text_similarity factor now uses cached
embedding cosine similarity whenever both the student and the project
have one, falling back to the original TF-IDF cosine similarity
otherwise. The factor's contract (0-1 raw score, explainable detail
string) is unchanged — every other factor, the dynamic renormalization,
and the public rank_* functions are untouched. ALGORITHM_VERSION bumped
rules_v2 -> hybrid_v3 to reflect the change.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

---

## Task 5: Synthetic-data vocabulary and deterministic generator core

**Files:**
- Create: `scripts/synthetic_data.py`
- Test: `tests/test_synthetic_data.py`

**Interfaces:**
- Produces: `synthetic_data.RNG_SEED: int`, `synthetic_data.DEGREE_POOL: list[tuple[str, str]]` (degree_title, primary ProjectCategory value), `synthetic_data.SKILLS_BY_CATEGORY: dict[str, list[str]]`, `synthetic_data.BUSINESS_TEMPLATES: list[dict]` (18 hand-authored businesses), `synthetic_data.PROJECT_TEMPLATES_BY_CATEGORY: dict[str, list[dict]]`, `synthetic_data.unique_email(rng, first, last, domain, used) -> str` — all consumed by Task 6/7/8's generator functions.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_synthetic_data.py
from scripts import synthetic_data as sd


def test_degree_pool_has_at_least_fifteen_entries_covering_every_category():
    assert len(sd.DEGREE_POOL) >= 15
    categories_covered = {category for _, category in sd.DEGREE_POOL}
    assert len(categories_covered) >= 5  # a healthy spread, not all piled into one category


def test_skills_by_category_covers_every_degree_pool_category():
    degree_categories = {category for _, category in sd.DEGREE_POOL}
    for category in degree_categories:
        assert category in sd.SKILLS_BY_CATEGORY
        assert len(sd.SKILLS_BY_CATEGORY[category]) >= 3


def test_business_templates_has_eighteen_unique_names_across_every_category():
    assert len(sd.BUSINESS_TEMPLATES) == 18
    names = [b["company_name"] for b in sd.BUSINESS_TEMPLATES]
    assert len(names) == len(set(names))
    categories = {b["category"] for b in sd.BUSINESS_TEMPLATES}
    assert len(categories) >= 5


def test_project_templates_exist_for_every_business_category():
    business_categories = {b["category"] for b in sd.BUSINESS_TEMPLATES}
    for category in business_categories:
        assert category in sd.PROJECT_TEMPLATES_BY_CATEGORY
        assert len(sd.PROJECT_TEMPLATES_BY_CATEGORY[category]) >= 1


def test_unique_email_avoids_collisions():
    used: set[str] = set()
    first = sd.unique_email(None, "Aisha", "Rahman", "manchester.ac.uk", used)
    second = sd.unique_email(None, "Aisha", "Rahman", "manchester.ac.uk", used)
    assert first != second
    assert first in used and second in used
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_synthetic_data.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'scripts.synthetic_data'`.

- [ ] **Step 3: Write the vocabulary and helpers**

```python
# scripts/synthetic_data.py
"""
Deterministic synthetic-data vocabulary and small helpers, used by
scripts/seed_demo_data.py (Workstream 9.a) to build a realistic-feeling
demo dataset. Deterministic (a fixed RNG seed) so reseeding produces the
same dataset every time — no drift between demo runs.
"""
import random

RNG_SEED = 20260913

FIRST_NAMES = [
    "Aisha", "Elif", "Femi", "Rosa", "Jack", "Sofia", "Liam", "Mia",
    "Omar", "Grace", "Noah", "Zara", "Ben", "Freya", "Ali", "Ruby",
    "Sam", "Isla", "Leo", "Amara", "Finn", "Nadia", "Josh", "Erin",
]

LAST_NAMES = [
    "Rahman", "Vasquez", "Okafor", "Lindqvist", "Doyle", "Petrova", "Nguyen",
    "Osei", "Fitzgerald", "Yamamoto", "Kaur", "Byrne", "Larsson", "Haddad",
    "Okoye", "Sullivan", "Ibrahim", "Novak", "Reilly", "Adeyemi", "Kowalski",
    "Blackwood", "Hassan", "Fenwick",
]

# NOTE: "Priya"/"Anand", "Tom"/"Whitfield", and "Ella"/"Marsh" are
# deliberately absent from the pools above — those three exact names are
# reserved for the hand-crafted hero-scenario students in
# scripts/seed_demo_data.py's _hero_students_data(), and must never be
# producible by the random generator (a coincidental duplicate would still
# get a de-duplicated email via unique_email(), but would confusingly
# imply two different people with the same name).

# (degree_title, primary ProjectCategory value) — degree titles are written
# to literally contain a "strong" keyword from
# app/services/matching/config.py's CATEGORY_KEYWORDS, so generated
# students score realistically against app/services/matching/degree.py.
DEGREE_POOL = [
    ("BSc Computer Science", "software_engineering"),
    ("BSc Data Science", "data_analytics"),
    ("BSc Software Engineering", "software_engineering"),
    ("MSc Data Analytics", "data_analytics"),
    ("BSc Statistics", "data_analytics"),
    ("BA Marketing", "marketing"),
    ("BA Communications", "marketing"),
    ("BA Media Studies", "marketing"),
    ("BA Graphic Design", "design"),
    ("BA Art", "design"),
    ("BSc Media Production", "design"),
    ("BSc Economics", "finance"),
    ("BSc Accounting and Finance", "finance"),
    ("BSc Business Management", "operations"),
    ("BSc Mathematics", "data_analytics"),
    ("BSc Environmental Science", "research"),
]

SKILLS_BY_CATEGORY = {
    "software_engineering": ["Python", "JavaScript", "React", "Node.js", "SQL", "Git", "Java", "TypeScript"],
    "data_analytics": ["Python", "SQL", "Statistics", "Machine Learning", "Data Visualisation", "Excel", "R", "Power BI"],
    "marketing": ["SEO", "Content Writing", "Social Media", "Google Analytics", "Email Marketing", "Copywriting"],
    "design": ["Figma", "Adobe Creative Suite", "UI", "UX", "Illustration", "Branding", "Prototyping"],
    "finance": ["Excel", "Financial Modelling", "Accounting", "Statistics"],
    "operations": ["Project Management", "Excel", "Process Improvement", "Stakeholder Management"],
    "research": ["Statistics", "R", "Data Visualisation", "Excel"],
}

# 18 hand-authored businesses, spread across categories so
# university-business agreements and generated projects have real variety.
# "Northbridge Analytics" is deliberately NOT in this list — that name is
# reserved for the hand-crafted hero account in seed_demo_data.py, which
# is a 19th, separate business (total businesses in the seeded dataset is
# 18 + 1 hero = 19, not 18).
BUSINESS_TEMPLATES = [
    {"company_name": "Riverstone Data Partners", "industry": "Data & Analytics Consultancy", "category": "data_analytics"},
    {"company_name": "Cascade Insights", "industry": "Market Research", "category": "data_analytics"},
    {"company_name": "Ledger & Loop", "industry": "Fintech Analytics", "category": "data_analytics"},
    {"company_name": "Foundry Software", "industry": "Software Development", "category": "software_engineering"},
    {"company_name": "Brightwell Digital", "industry": "Web & App Development", "category": "software_engineering"},
    {"company_name": "Kestrel Systems", "industry": "Enterprise Software", "category": "software_engineering"},
    {"company_name": "Marlow & Finch", "industry": "Marketing Agency", "category": "marketing"},
    {"company_name": "Loudmouth Media", "industry": "Social Media Marketing", "category": "marketing"},
    {"company_name": "Hearth Brand Studio", "industry": "Brand Strategy", "category": "marketing"},
    {"company_name": "Fernhollow Studio", "industry": "Design Agency", "category": "design"},
    {"company_name": "Paperclip Creative", "industry": "Graphic Design", "category": "design"},
    {"company_name": "Willowmere Design Co.", "industry": "Product Design", "category": "design"},
    {"company_name": "Amberly Finance Partners", "industry": "Financial Services", "category": "finance"},
    {"company_name": "Northstone Accounting", "industry": "Accounting", "category": "finance"},
    {"company_name": "Greybridge Logistics", "industry": "Logistics & Operations", "category": "operations"},
    {"company_name": "Hollowfield Ops", "industry": "Operations Consultancy", "category": "operations"},
    {"company_name": "Bramwell Environmental", "industry": "Environmental Consultancy", "category": "research"},
    {"company_name": "Sable Research Collective", "industry": "Independent Research", "category": "research"},
]

PROJECT_TEMPLATES_BY_CATEGORY = {
    "data_analytics": [
        {"title": "Customer Churn Analysis", "description": "Analyse subscription data to identify the top drivers of customer churn.", "required_skills": ["Python", "SQL", "Statistics"], "duration_label": "1-2 weeks", "estimated_hours": 15, "hourly_rate_gbp": 19},
        {"title": "Sales Dashboard Build", "description": "Build an interactive dashboard visualising regional sales trends for the leadership team.", "required_skills": ["SQL", "Data Visualisation", "Excel"], "duration_label": "2-3 weeks", "estimated_hours": 20, "hourly_rate_gbp": 20},
    ],
    "software_engineering": [
        {"title": "Internal Tools Prototype", "description": "Build a small internal web tool to replace a manual spreadsheet workflow.", "required_skills": ["Python", "JavaScript", "SQL"], "duration_label": "2-3 weeks", "estimated_hours": 18, "hourly_rate_gbp": 21},
        {"title": "API Integration", "description": "Integrate a third-party payments API into our existing backend service.", "required_skills": ["Python", "Git"], "duration_label": "1-2 weeks", "estimated_hours": 14, "hourly_rate_gbp": 22},
    ],
    "marketing": [
        {"title": "SEO Content Audit", "description": "Audit our existing site content and propose an SEO improvement plan.", "required_skills": ["SEO", "Content Writing"], "duration_label": "1 week", "estimated_hours": 10, "hourly_rate_gbp": 17},
        {"title": "Social Campaign Plan", "description": "Plan and schedule a month-long social media campaign for a product launch.", "required_skills": ["Social Media", "Copywriting"], "duration_label": "1-2 weeks", "estimated_hours": 12, "hourly_rate_gbp": 17},
    ],
    "design": [
        {"title": "Brand Refresh", "description": "Refresh our logo and brand guidelines for a more modern look.", "required_skills": ["Figma", "Branding"], "duration_label": "2 weeks", "estimated_hours": 16, "hourly_rate_gbp": 18},
        {"title": "App UI Redesign", "description": "Redesign our mobile app's onboarding flow for clarity and accessibility.", "required_skills": ["Figma", "UI", "UX"], "duration_label": "2-3 weeks", "estimated_hours": 18, "hourly_rate_gbp": 19},
    ],
    "finance": [
        {"title": "Budget Model Build", "description": "Build a rolling 12-month budget model in a spreadsheet for our finance team.", "required_skills": ["Excel", "Financial Modelling"], "duration_label": "1-2 weeks", "estimated_hours": 14, "hourly_rate_gbp": 19},
    ],
    "operations": [
        {"title": "Process Mapping", "description": "Map and document our order-fulfilment process to find efficiency gains.", "required_skills": ["Process Improvement", "Excel"], "duration_label": "1-2 weeks", "estimated_hours": 12, "hourly_rate_gbp": 17},
    ],
    "research": [
        {"title": "Literature Review", "description": "Conduct a literature review on sustainable packaging alternatives.", "required_skills": ["Statistics", "Data Visualisation"], "duration_label": "1-2 weeks", "estimated_hours": 12, "hourly_rate_gbp": 17},
    ],
}


def unique_email(rng: "random.Random | None", first: str, last: str, domain: str, used: set[str]) -> str:
    """Builds first.last@domain, appending a numeric suffix on collision.
    `rng` is accepted for interface consistency with the other generator
    functions but isn't actually needed here — collisions are resolved
    deterministically by counting up, not by rerolling."""
    base = f"{first.lower()}.{last.lower()}@{domain}"
    if base not in used:
        used.add(base)
        return base
    n = 2
    while f"{first.lower()}.{last.lower()}{n}@{domain}" in used:
        n += 1
    email = f"{first.lower()}.{last.lower()}{n}@{domain}"
    used.add(email)
    return email
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_synthetic_data.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add scripts/synthetic_data.py tests/test_synthetic_data.py
git commit -m "$(cat <<'EOF'
Add synthetic-data vocabulary for the demo seed script (Workstream 9.a.i)

Name pools, a 16-entry degree pool whose titles literally contain the
existing CATEGORY_KEYWORDS "strong" phrases (so generated students
score realistically against the real degree-relevance logic),
per-category skill pools overlapping SKILL_SYNONYMS, 18 hand-authored
businesses, and project brief templates per category. Deterministic
(RNG_SEED) — the actual generator functions land in the next task.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

---

## Task 6: Student generator function

**Files:**
- Modify: `scripts/synthetic_data.py`
- Test: `tests/test_synthetic_data.py` (extend)

**Interfaces:**
- Consumes: `DEGREE_POOL`, `SKILLS_BY_CATEGORY`, `FIRST_NAMES`, `LAST_NAMES`, `unique_email` from Task 5.
- Produces: `synthetic_data.generate_students(rng: random.Random, universities: list, count: int, used_emails: set[str]) -> list[StudentProfile-shaped dict]` — a list of plain dicts with keys matching `StudentProfile`'s constructor kwargs (minus `user_id`, which the caller assigns after creating the `User` row) plus a `full_name` and `email` for the paired `User` row. Consumed by Task 9's seed script.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_synthetic_data.py — append
from app.models.enums import StudentBand
from scripts import synthetic_data as sd


class _FakeUniversity:
    def __init__(self, id_, domain):
        self.id = id_
        self.domain = domain


def test_generate_students_returns_the_requested_count_with_valid_fields():
    rng = sd.random.Random(sd.RNG_SEED)
    universities = [_FakeUniversity("uni-1", "manchester.ac.uk"), _FakeUniversity("uni-2", "leeds.ac.uk")]
    used_emails: set[str] = set()

    students = sd.generate_students(rng, universities, count=40, used_emails=used_emails)

    assert len(students) == 40
    emails = [s["email"] for s in students]
    assert len(emails) == len(set(emails))  # no duplicates
    for s in students:
        assert s["university_id"] in {"uni-1", "uni-2"}
        assert s["degree_title"] in {title for title, _ in sd.DEGREE_POOL}
        assert isinstance(s["band"], StudentBand)
        assert 1 <= len(s["skills"]) <= 6
        assert 0.0 <= s.get("average_rating", 0.0) <= 5.0


def test_generate_students_is_deterministic_for_a_fixed_seed():
    universities = [_FakeUniversity("uni-1", "manchester.ac.uk")]
    students_a = sd.generate_students(sd.random.Random(sd.RNG_SEED), universities, count=10, used_emails=set())
    students_b = sd.generate_students(sd.random.Random(sd.RNG_SEED), universities, count=10, used_emails=set())
    assert [s["email"] for s in students_a] == [s["email"] for s in students_b]
    assert [s["skills"] for s in students_a] == [s["skills"] for s in students_b]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_synthetic_data.py -k generate_students -v`
Expected: FAIL — `AttributeError: module 'scripts.synthetic_data' has no attribute 'generate_students'`.

- [ ] **Step 3: Write the implementation**

Append to `scripts/synthetic_data.py`:

```python
from app.models.enums import StudentBand

# Weighted toward the bands most agreements actually grant access to,
# so most generated students are visible to most generated businesses —
# a handful of early-years students still exist for realism, they just
# won't show up on every shortlist.
_BAND_WEIGHTS = [
    (StudentBand.YEAR_1, 0.05),
    (StudentBand.YEAR_2, 0.20),
    (StudentBand.YEAR_3, 0.30),
    (StudentBand.YEAR_4_PLUS, 0.20),
    (StudentBand.POSTGRAD_TAUGHT, 0.20),
    (StudentBand.POSTGRAD_RESEARCH, 0.05),
]


def _weighted_choice(rng: random.Random, weighted_options: list[tuple]):
    options, weights = zip(*weighted_options)
    return rng.choices(options, weights=weights, k=1)[0]


def generate_students(rng: random.Random, universities: list, count: int, used_emails: set[str]) -> list[dict]:
    """Returns `count` dicts, each shaped for **kwargs into StudentProfile
    (plus 'full_name' and 'email' for the paired User row) — the caller
    creates the User, flushes for its id, then builds the StudentProfile
    from the remaining keys."""
    students = []
    for _ in range(count):
        first = rng.choice(FIRST_NAMES)
        last = rng.choice(LAST_NAMES)
        university = rng.choice(universities)
        degree_title, category = rng.choice(DEGREE_POOL)
        band = _weighted_choice(rng, _BAND_WEIGHTS)

        pool = SKILLS_BY_CATEGORY[category]
        num_skills = rng.randint(2, min(5, len(pool)))
        skills = rng.sample(pool, num_skills)
        # Small chance of one extra skill from an unrelated category —
        # real students aren't purely one-dimensional.
        if rng.random() < 0.2:
            other_category = rng.choice([c for c in SKILLS_BY_CATEGORY if c != category])
            skills.append(rng.choice(SKILLS_BY_CATEGORY[other_category]))

        has_track_record = rng.random() < 0.6
        completed_projects_count = rng.randint(1, 8) if has_track_record else 0
        average_rating = round(rng.uniform(3.8, 5.0), 1) if has_track_record else 0.0

        students.append({
            "email": unique_email(rng, first, last, university.domain, used_emails),
            "full_name": f"{first} {last}",
            "university_id": university.id,
            "degree_title": degree_title,
            "band": band,
            "modules": rng.sample(pool, min(2, len(pool))),
            "skills": skills,
            "hourly_rate_expectation_gbp": round(rng.uniform(15.0, 25.0), 2),
            "weekly_hours_available": rng.randint(5, 20),
            "is_id_verified": rng.random() < 0.6,
            "average_rating": average_rating,
            "completed_projects_count": completed_projects_count,
            "on_time_rate": round(rng.uniform(0.85, 1.0), 2) if has_track_record else 0.0,
        })
    return students
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_synthetic_data.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add scripts/synthetic_data.py tests/test_synthetic_data.py
git commit -m "$(cat <<'EOF'
Add deterministic synthetic student generator (Workstream 9.a.ii)

generate_students() produces realistic, varied student profiles —
degree/category-consistent skills and modules, a band distribution
weighted toward the bands agreements typically grant, and a mix of
brand-new vs. experienced reputations. Same RNG seed always produces
the same dataset.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

---

## Task 7: Business + university-agreement generator function

**Files:**
- Modify: `scripts/synthetic_data.py`
- Test: `tests/test_synthetic_data.py` (extend)

**Interfaces:**
- Consumes: `BUSINESS_TEMPLATES` from Task 5.
- Produces: `synthetic_data.generate_businesses(rng, universities: list, used_emails: set[str]) -> list[dict]` — each dict has `email`, `full_name` (hiring-team contact name), plus `BusinessProfile` kwargs, plus an `"agreements"` key: a list of `{"university_id": ..., "allowed_bands": [...], "allowed_categories": [...]}` dicts (1-3 partner universities per business, weighted toward whichever university is passed first — the seed script will pass Manchester first). Consumed by Task 9's seed script.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_synthetic_data.py — append
def test_generate_businesses_returns_one_entry_per_template_with_at_least_one_agreement():
    rng = sd.random.Random(sd.RNG_SEED)
    universities = [_FakeUniversity("uni-1", "manchester.ac.uk"), _FakeUniversity("uni-2", "leeds.ac.uk")]
    businesses = sd.generate_businesses(rng, universities, used_emails=set())

    assert len(businesses) == len(sd.BUSINESS_TEMPLATES)
    for b in businesses:
        assert 1 <= len(b["agreements"]) <= len(universities)
        for agreement in b["agreements"]:
            assert agreement["university_id"] in {"uni-1", "uni-2"}
            assert b["category"] in agreement["allowed_categories"]
            assert len(agreement["allowed_bands"]) >= 1


def test_generate_businesses_favours_the_first_university_passed():
    rng = sd.random.Random(sd.RNG_SEED)
    universities = [_FakeUniversity("uni-primary", "manchester.ac.uk"), _FakeUniversity("uni-2", "leeds.ac.uk"), _FakeUniversity("uni-3", "sheffield.ac.uk")]
    businesses = sd.generate_businesses(rng, universities, used_emails=set())
    covering_primary = sum(
        1 for b in businesses if any(a["university_id"] == "uni-primary" for a in b["agreements"])
    )
    # Not every business needs to partner with the primary university, but
    # most should, given it's weighted first.
    assert covering_primary >= len(businesses) * 0.6
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_synthetic_data.py -k generate_businesses -v`
Expected: FAIL — `AttributeError`.

- [ ] **Step 3: Write the implementation**

Append to `scripts/synthetic_data.py`:

```python
_AGREEMENT_BANDS = [b.value for b in [StudentBand.YEAR_2, StudentBand.YEAR_3, StudentBand.YEAR_4_PLUS, StudentBand.POSTGRAD_TAUGHT]]


def generate_businesses(rng: random.Random, universities: list, used_emails: set[str]) -> list[dict]:
    """Returns one dict per BUSINESS_TEMPLATES entry, each with an
    'agreements' list describing 1-3 partner universities. The first
    university in `universities` is weighted to appear in most
    businesses' agreements (pass the demo's home university first)."""
    businesses = []
    for template in BUSINESS_TEMPLATES:
        first, last = rng.choice(FIRST_NAMES), rng.choice(LAST_NAMES)
        num_partners = rng.choices([1, 2, 3], weights=[0.3, 0.4, 0.3], k=1)[0]
        num_partners = min(num_partners, len(universities))

        partners = [universities[0]] if rng.random() < 0.7 else []
        remaining = [u for u in universities if u not in partners]
        rng.shuffle(remaining)
        for uni in remaining:
            if len(partners) >= num_partners:
                break
            partners.append(uni)
        if not partners:  # the 30% roll above skipped the primary and nothing else got picked
            partners = [rng.choice(universities)]

        agreements = [
            {
                "university_id": uni.id,
                "allowed_bands": list(_AGREEMENT_BANDS),
                "allowed_categories": [template["category"]],
            }
            for uni in partners
        ]

        company_slug = template["company_name"].lower().replace(" ", "-").replace("&", "and").replace(".", "")
        businesses.append({
            "email": unique_email(rng, "hello", company_slug, "example.com", used_emails),
            "full_name": f"{first} {last}",
            "company_name": template["company_name"],
            "industry": template["industry"],
            "category": template["category"],
            "company_registration_number": str(rng.randint(10_000_000, 99_999_999)),
            "agreements": agreements,
        })
    return businesses
```

Note: `unique_email` builds `hello.{company_slug}@example.com`-shaped addresses since its signature is `(first, last, domain, used)` — that's fine, it's just building a plausible business contact address, not literally a person's name.

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_synthetic_data.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add scripts/synthetic_data.py tests/test_synthetic_data.py
git commit -m "$(cat <<'EOF'
Add synthetic business + university-agreement generator (Workstream 9.a.ii)

generate_businesses() pairs each of the 18 hand-authored businesses
with 1-3 partner universities (weighted toward whichever university
the caller passes first), each an APPROVED agreement covering that
business's category and the bands most agreements grant in practice.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

---

## Task 8: Project generator function

**Files:**
- Modify: `scripts/synthetic_data.py`
- Test: `tests/test_synthetic_data.py` (extend)

**Interfaces:**
- Consumes: `PROJECT_TEMPLATES_BY_CATEGORY` from Task 5, the `businesses` list shape produced by Task 7.
- Produces: `synthetic_data.generate_projects(rng, businesses: list[dict], target_count: int) -> list[dict]` — each dict has `business_index` (index into the `businesses` list the caller passed in, so it can look up the real `BusinessProfile.id` after those rows are committed) plus `Project` constructor kwargs (`target_university_ids`/`target_bands` drawn from that business's own agreements, so every generated project is guaranteed postable). Consumed by Task 9's seed script.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_synthetic_data.py — append
def test_generate_projects_only_targets_universities_and_bands_the_business_is_approved_for():
    rng = sd.random.Random(sd.RNG_SEED)
    universities = [_FakeUniversity("uni-1", "manchester.ac.uk"), _FakeUniversity("uni-2", "leeds.ac.uk")]
    businesses = sd.generate_businesses(rng, universities, used_emails=set())

    projects = sd.generate_projects(rng, businesses, target_count=25)

    assert 20 <= len(projects) <= 30  # "around" target_count, template pool size can nudge it
    for project in projects:
        business = businesses[project["business_index"]]
        approved_uni_ids = {a["university_id"] for a in business["agreements"]}
        approved_bands = set().union(*(set(a["allowed_bands"]) for a in business["agreements"]))
        assert set(project["target_university_ids"]) <= approved_uni_ids
        assert set(project["target_bands"]) <= approved_bands
        assert project["category"] == business["category"]


def test_generate_projects_is_deterministic_for_a_fixed_seed():
    universities = [_FakeUniversity("uni-1", "manchester.ac.uk")]
    businesses = sd.generate_businesses(sd.random.Random(sd.RNG_SEED), universities, used_emails=set())
    projects_a = sd.generate_projects(sd.random.Random(sd.RNG_SEED), businesses, target_count=20)
    projects_b = sd.generate_projects(sd.random.Random(sd.RNG_SEED), businesses, target_count=20)
    assert [p["title"] for p in projects_a] == [p["title"] for p in projects_b]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_synthetic_data.py -k generate_projects -v`
Expected: FAIL — `AttributeError`.

- [ ] **Step 3: Write the implementation**

Append to `scripts/synthetic_data.py`:

```python
from app.models.enums import ProjectCategory


def generate_projects(rng: random.Random, businesses: list[dict], target_count: int) -> list[dict]:
    """Returns roughly `target_count` project dicts, distributed across
    `businesses` (each business posts 1-2), every one targeting only
    university/band combinations that business's own generated agreements
    actually approve — so every generated project is guaranteed postable
    without a 403."""
    projects = []
    business_indices = list(range(len(businesses)))
    rng.shuffle(business_indices)

    while len(projects) < target_count:
        for business_index in business_indices:
            if len(projects) >= target_count:
                break
            business = businesses[business_index]
            templates = PROJECT_TEMPLATES_BY_CATEGORY[business["category"]]
            template = rng.choice(templates)

            # Restrict to a random non-empty subset of this business's own
            # approved universities/bands — never targets anything it isn't
            # actually approved for.
            approved_universities = [a["university_id"] for a in business["agreements"]]
            num_target_unis = rng.randint(1, len(approved_universities))
            target_university_ids = rng.sample(approved_universities, num_target_unis)

            approved_bands = sorted(set().union(*(set(a["allowed_bands"]) for a in business["agreements"])))
            num_target_bands = rng.randint(1, len(approved_bands))
            target_bands = rng.sample(approved_bands, num_target_bands)

            projects.append({
                "business_index": business_index,
                "title": template["title"],
                "description": template["description"],
                "category": ProjectCategory(business["category"]),
                "required_skills": list(template["required_skills"]),
                "duration_label": template["duration_label"],
                "estimated_hours": template["estimated_hours"],
                "hourly_rate_gbp": template["hourly_rate_gbp"],
                "target_university_ids": target_university_ids,
                "target_bands": target_bands,
            })
    return projects
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_synthetic_data.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add scripts/synthetic_data.py tests/test_synthetic_data.py
git commit -m "$(cat <<'EOF'
Add synthetic project generator (Workstream 9.a.ii)

generate_projects() distributes ~25 projects across the 18 generated
businesses, each drawn from a category-matched brief template and
restricted to only the universities/bands that business's own
generated agreement actually approves — every generated project is
guaranteed to post successfully, never a 403.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

---

## Task 9: Hero demo account + full seed script rewrite

**Files:**
- Modify: `scripts/seed_demo_data.py`
- Test: `tests/test_seed_demo_data.py`

**Interfaces:**
- Consumes: `synthetic_data.generate_students/generate_businesses/generate_projects`, `matching.refresh_student_embedding/refresh_project_embedding`.
- Produces: `seed_demo_data.run(db: Optional[Session] = None) -> SeedSummary` (a small dataclass: `universities: int`, `students: int`, `businesses: int`, `projects: int`, `hero_business_email: str`, `hero_business_password: str`) — consumed by Task 10's e2e test and by anyone running the script manually.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_seed_demo_data.py
"""Workstream 9.a.iii/9.a.iv — the rewritten seed script builds a small
but varied synthetic dataset plus one hand-crafted "hero" business account
(Northbridge Analytics) with a pool of Manchester students engineered to
produce a clearly differentiated shortlist once a project is posted
against them (verified for real in Task 10/11 — this test just checks the
data landed correctly)."""
from app.models.policy import UniversityBusinessAgreement
from app.models.project import Project
from app.models.university import University
from app.models.user import BusinessProfile, StudentProfile, User
from scripts import seed_demo_data


def test_seed_creates_a_realistic_small_dataset(db_session):
    summary = seed_demo_data.run(db=db_session)

    assert summary.universities == 4
    assert 60 <= summary.students <= 100
    assert summary.businesses == 19  # 18 generated (BUSINESS_TEMPLATES) + 1 hand-crafted hero
    assert 20 <= summary.projects <= 30

    assert db_session.query(University).count() == summary.universities
    assert db_session.query(StudentProfile).count() == summary.students
    assert db_session.query(BusinessProfile).count() == summary.businesses
    assert db_session.query(Project).count() == summary.projects
    assert db_session.query(UniversityBusinessAgreement).count() >= summary.businesses  # at least 1 each


def test_seed_creates_the_hero_business_with_an_approved_manchester_agreement(db_session):
    summary = seed_demo_data.run(db=db_session)

    hero_user = db_session.query(User).filter(User.email == summary.hero_business_email).first()
    assert hero_user is not None
    hero_business = db_session.query(BusinessProfile).filter(BusinessProfile.user_id == hero_user.id).first()
    assert hero_business.company_name == "Northbridge Analytics"

    manchester = db_session.query(University).filter(University.slug == "manchester").first()
    agreement = (
        db_session.query(UniversityBusinessAgreement)
        .filter(
            UniversityBusinessAgreement.business_id == hero_business.id,
            UniversityBusinessAgreement.university_id == manchester.id,
        )
        .first()
    )
    assert agreement is not None
    assert agreement.status.value == "approved"
    assert not agreement.requires_university_project_review


def test_seed_hand_crafted_students_have_differentiated_profiles_for_the_hero_scenario(db_session):
    summary = seed_demo_data.run(db=db_session)
    top_match = db_session.query(User).filter(User.email == "priya.anand@manchester.ac.uk").first()
    assert top_match is not None
    top_profile = db_session.query(StudentProfile).filter(StudentProfile.user_id == top_match.id).first()
    assert set(["Python", "SQL", "React"]).issubset(set(top_profile.skills))
    assert "Data Science" in top_profile.degree_title


def test_seed_is_idempotent_and_safe_to_rerun(db_session):
    """run()'s actual "safe to rerun" guarantee only applies when it owns
    its own session (the real `python -m scripts.seed_demo_data` usage,
    which drops and recreates every table via Base.metadata.drop_all +
    run_migrations before reseeding — see run()'s owns_session branch).
    Passing an existing `db` in (as every other test in this file does)
    deliberately skips that reset, since the db_session fixture already
    hands over a fresh, empty database every time — there's nothing to
    wipe. This test simulates one real reseed cycle by wiping the schema
    itself between two calls, the same way the script's own reset does,
    and checks the result is identical both times (same RNG seed -> same
    dataset, not a coincidence)."""
    from app.db.base_class import Base
    from app.models.user import BusinessProfile

    first = seed_demo_data.run(db=db_session)

    bind = db_session.get_bind()
    Base.metadata.drop_all(bind=bind)
    Base.metadata.create_all(bind=bind)

    second = seed_demo_data.run(db=db_session)
    assert first.students == second.students
    assert first.businesses == second.businesses
    assert db_session.query(BusinessProfile).count() == second.businesses
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_seed_demo_data.py -v`
Expected: FAIL — `seed_demo_data.run` doesn't accept a `db` kwarg yet, and doesn't produce anywhere near this dataset shape.

- [ ] **Step 3: Rewrite `scripts/seed_demo_data.py`**

```python
"""
Seed script — wipes and rebuilds a small, realistic synthetic demo
dataset: 4 universities, ~80 students, 19 businesses (18 generated, each
with 1-3 university partnership agreements, plus one hand-crafted "hero"
business account — Northbridge Analytics, at the University of
Manchester), and ~25 projects. The hero's surrounding Manchester student
pool is engineered to produce a clearly differentiated shortlist once a
project brief is posted against it — see
caplink/docs/superpowers/specs/2026-09-13-demo-realism-matching-uplift-design.md.

Safe to rerun any time: always drops and recreates every table first, so
this never accumulates duplicates across repeated demo/pitch resets.
Deterministic (scripts.synthetic_data.RNG_SEED) — the same dataset every
run.

Run with:  python -m scripts.seed_demo_data
"""
import random
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.db.base_class import Base
from app.db.migrations import run_migrations
from app.db.session import SessionLocal, engine
from app.models.enums import (
    AgreementStatus,
    BusinessTrustTier,
    ProjectCategory,
    ProjectStatus,
    StudentBand,
    UniversityLicenseStatus,
    UniversityLicenseTier,
    UserRole,
)
from app.models.policy import UniversityBusinessAgreement
from app.models.project import Project
from app.models.university import University
from app.models.user import BusinessProfile, StudentProfile, User
from app.services import matching
from scripts import synthetic_data

import app.models  # noqa: F401

DEMO_PASSWORD = "ChangeMe123!"

# (name, slug, domain, postcode, lat, lon) — real, well-known campus
# coordinates used only illustratively (see the marketing site's own
# "Not affiliated with any university shown for illustration" footer note).
_UNIVERSITY_SEEDS = [
    ("University of Manchester", "manchester", "manchester.ac.uk", "M13 9PL", 53.4668, -2.2339),
    ("University of Leeds", "leeds", "leeds.ac.uk", "LS2 9JT", 53.8067, -1.5550),
    ("University of Sheffield", "sheffield", "sheffield.ac.uk", "S10 2TN", 53.3811, -1.4870),
    ("Manchester Metropolitan University", "manchester-met", "mmu.ac.uk", "M15 6BH", 53.4715, -2.2445),
]


@dataclass
class SeedSummary:
    universities: int
    students: int
    businesses: int
    projects: int
    hero_business_email: str
    hero_business_password: str


def _create_universities(db: Session) -> list[University]:
    universities = []
    for name, slug, domain, postcode, lat, lon in _UNIVERSITY_SEEDS:
        university = University(
            name=name, slug=slug, domain=domain, primary_color="#1B2A45",
            license_tier=UniversityLicenseTier.ENTERPRISE, license_status=UniversityLicenseStatus.ACTIVE,
            license_seats=5000, primary_contact_name="Careers & Employability Service",
            primary_contact_email=f"careers@{domain}", postcode=postcode, latitude=lat, longitude=lon,
        )
        db.add(university)
        universities.append(university)
    db.flush()
    return universities


def _create_admin(db: Session, university: University) -> User:
    admin = User(
        email=f"admin@{university.domain}", hashed_password=hash_password(DEMO_PASSWORD),
        role=UserRole.UNIVERSITY_ADMIN, full_name="Careers Service Admin",
        university_id=university.id, is_email_verified=True,
    )
    db.add(admin)
    return admin


def _create_student(db: Session, data: dict) -> StudentProfile:
    user = User(
        email=data["email"], hashed_password=hash_password(DEMO_PASSWORD), role=UserRole.STUDENT,
        full_name=data["full_name"], university_id=data["university_id"], is_email_verified=True,
    )
    db.add(user)
    db.flush()
    profile = StudentProfile(
        user_id=user.id, university_id=data["university_id"], degree_title=data["degree_title"],
        band=data["band"], data_sharing_consent_at=datetime.utcnow(), modules=data["modules"],
        skills=data["skills"], hourly_rate_expectation_gbp=data["hourly_rate_expectation_gbp"],
        weekly_hours_available=data["weekly_hours_available"], is_id_verified=data["is_id_verified"],
        average_rating=data["average_rating"], completed_projects_count=data["completed_projects_count"],
        on_time_rate=data["on_time_rate"],
    )
    matching.refresh_student_embedding(profile)
    db.add(profile)
    return profile


def _create_business(db: Session, data: dict, admin_by_university: dict[str, User]) -> BusinessProfile:
    user = User(
        email=data["email"], hashed_password=hash_password(DEMO_PASSWORD), role=UserRole.BUSINESS,
        full_name=data["full_name"], is_email_verified=True,
    )
    db.add(user)
    db.flush()
    business = BusinessProfile(
        user_id=user.id, company_name=data["company_name"], company_registration_number=data["company_registration_number"],
        industry=data["industry"], global_trust_tier=BusinessTrustTier.UNIVERSITY_APPROVED, is_registration_verified=True,
    )
    db.add(business)
    db.flush()
    for agreement in data["agreements"]:
        db.add(UniversityBusinessAgreement(
            university_id=agreement["university_id"], business_id=business.id, status=AgreementStatus.APPROVED,
            allowed_bands=agreement["allowed_bands"], allowed_categories=agreement["allowed_categories"],
            requires_university_project_review=False,
            reviewed_by_admin_id=admin_by_university[agreement["university_id"]].id,
        ))
    return business


def _create_project(db: Session, data: dict, business_id: str) -> Project:
    project = Project(
        business_id=business_id, title=data["title"], description=data["description"], category=data["category"],
        required_skills=data["required_skills"], duration_label=data["duration_label"],
        estimated_hours=data["estimated_hours"], hourly_rate_gbp=data["hourly_rate_gbp"], is_remote=True,
        target_university_ids=data["target_university_ids"], target_bands=data["target_bands"],
        status=ProjectStatus.OPEN,
    )
    matching.refresh_project_embedding(project)
    db.add(project)
    return project


def _hero_business_data() -> dict:
    """Northbridge Analytics — the "hero" account for a live pitch demo.
    Its own project is deliberately NOT pre-seeded: the whole point of the
    demo is posting one live (see Task 11's browser verification and the
    printed suggested brief below) and watching real, differentiated
    matches come back."""
    return {
        "email": "demo.business@example.com",
        "full_name": "Northbridge Analytics Hiring Team",
        "company_name": "Northbridge Analytics",
        "industry": "Data & Analytics Consultancy",
        "company_registration_number": "10293847",
    }


def _hero_students_data(manchester_id: str) -> list[dict]:
    """Three hand-crafted Manchester students engineered to produce a
    clear best-to-weakest match story once "Build a customer analytics
    dashboard" (see the printed suggested brief) is posted against them —
    on top of whichever generically-generated Manchester students also
    end up on the same shortlist."""
    return [
        {  # ~90%+: exact skill overlap, strong degree match, real track record
            "email": "priya.anand@manchester.ac.uk", "full_name": "Priya Anand", "university_id": manchester_id,
            "degree_title": "BSc Data Science", "band": StudentBand.YEAR_3,
            "modules": ["Machine Learning", "Databases", "Statistics II"],
            "skills": ["Python", "SQL", "React", "Data Visualisation"],
            "hourly_rate_expectation_gbp": 20.0, "weekly_hours_available": 15,
            "is_id_verified": True, "average_rating": 4.8, "completed_projects_count": 3, "on_time_rate": 1.0,
        },
        {  # ~75-85%: strong degree match, partial skill overlap
            "email": "tom.whitfield@manchester.ac.uk", "full_name": "Tom Whitfield", "university_id": manchester_id,
            "degree_title": "BSc Computer Science", "band": StudentBand.YEAR_4_PLUS,
            "modules": ["Algorithms", "Web Development"],
            "skills": ["Python", "JavaScript", "SQL"],
            "hourly_rate_expectation_gbp": 21.0, "weekly_hours_available": 10,
            "is_id_verified": True, "average_rating": 4.5, "completed_projects_count": 1, "on_time_rate": 1.0,
        },
        {  # ~40-60%: no degree relevance, no direct skill overlap — the weak tail
            "email": "ella.marsh@manchester.ac.uk", "full_name": "Ella Marsh", "university_id": manchester_id,
            "degree_title": "BA Marketing", "band": StudentBand.YEAR_3,
            "modules": ["Digital Marketing", "Consumer Behaviour"],
            "skills": ["SEO", "Content Writing", "Excel"],
            "hourly_rate_expectation_gbp": 18.0, "weekly_hours_available": 12,
            "is_id_verified": False, "average_rating": 4.2, "completed_projects_count": 2, "on_time_rate": 0.95,
        },
    ]


def run(db: Optional[Session] = None) -> SeedSummary:
    owns_session = db is None
    if owns_session:
        Base.metadata.drop_all(engine)
        run_migrations(engine)
        db = SessionLocal()

    rng = random.Random(synthetic_data.RNG_SEED)
    used_emails: set[str] = set()

    universities = _create_universities(db)
    admin_by_university = {u.id: _create_admin(db, u) for u in universities}
    db.flush()
    manchester = next(u for u in universities if u.slug == "manchester")

    student_data = synthetic_data.generate_students(rng, universities, count=77, used_emails=used_emails)
    hero_students = _hero_students_data(manchester.id)
    used_emails.update(d["email"] for d in hero_students)  # reserve these before any business emails are generated
    student_data += hero_students
    for data in student_data:
        _create_student(db, data)

    business_data = synthetic_data.generate_businesses(rng, universities, used_emails=used_emails)
    hero_data = _hero_business_data()
    used_emails.add(hero_data["email"])
    business_data.append({**hero_data, "category": "data_analytics", "agreements": [{
        "university_id": manchester.id,
        "allowed_bands": [StudentBand.YEAR_3.value, StudentBand.YEAR_4_PLUS.value, StudentBand.POSTGRAD_TAUGHT.value],
        "allowed_categories": [ProjectCategory.DATA_ANALYTICS.value, ProjectCategory.SOFTWARE_ENGINEERING.value],
    }]})
    db.flush()
    businesses = [_create_business(db, data, admin_by_university) for data in business_data]
    db.flush()

    business_id_by_index = {i: b.id for i, b in enumerate(businesses)}
    # generate_projects only ever sees the generated (non-hero) businesses —
    # slice them off before generating so indices line up, then skip the
    # hero's own index (it posts its project live, not via this script).
    generated_businesses = business_data[:-1]
    project_data = synthetic_data.generate_projects(rng, generated_businesses, target_count=25)
    for data in project_data:
        _create_project(db, data, business_id_by_index[data["business_index"]])

    db.commit()
    summary = SeedSummary(
        universities=len(universities), students=len(student_data), businesses=len(businesses),
        projects=len(project_data), hero_business_email=hero_data["email"], hero_business_password=DEMO_PASSWORD,
    )
    if owns_session:
        db.close()
    return summary


if __name__ == "__main__":
    result = run()
    print(f"Seed complete: {result.universities} universities, {result.students} students, "
          f"{result.businesses} businesses, {result.projects} projects.")
    print(f"Hero business login: {result.hero_business_email} / {result.hero_business_password}")
    print("Suggested demo project brief for the hero account (post this live during a pitch):")
    print("  Title: Build a customer analytics dashboard")
    print("  Description: We need an interactive dashboard that visualises customer engagement, "
          "retention and revenue trends from our subscription data, so our team can make faster, "
          "data-informed decisions without waiting on manual reports.")
    print("  Category: data_analytics | Required skills: Python, SQL, Data Visualisation, React")
    print("  Duration: 2-3 weeks | Estimated hours: 20 | Rate: £22/hr")
    print("  Target: University of Manchester | Bands: year_3, year_4_plus, postgrad_taught")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_seed_demo_data.py -v`
Expected: PASS.

- [ ] **Step 5: Run the full test suite**

Run: `pytest -x -q`
Expected: PASS.

- [ ] **Step 6: Manually run the script and read the output**

Run: `python -m scripts.seed_demo_data`
Expected: prints the summary line, the hero login, and the suggested demo project brief, with no errors. (This will drop and recreate every table in whatever `DATABASE_URL` your `.env` points at — confirm that's your local dev DB, not staging, before running it directly. Task 12 covers the safe reset workflow for staging/pitch use explicitly.)

- [ ] **Step 7: Commit**

```bash
git add scripts/seed_demo_data.py tests/test_seed_demo_data.py
git commit -m "$(cat <<'EOF'
Rewrite seed_demo_data.py around the synthetic-data generators (Workstream 9.a.iii/iv)

Replaces the old one-of-everything seed with 4 universities, ~80
students, 19 businesses (18 generated with real university partnership
agreements, plus a hand-crafted "Northbridge Analytics" hero account),
~25 projects, and 3 hand-crafted Manchester students engineered for a
clearly differentiated shortlist. The hero's own project is
deliberately NOT pre-seeded — posting it live is the point of the demo
(see the printed suggested brief and Task 11's browser verification).
Idempotent: always drops and recreates every table first, so reruns
never accumulate duplicates.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

---

## Task 10: E2E sanity test — differentiated matches via real HTTP

**Files:**
- Test: `tests/test_synthetic_dataset_matches_e2e.py`

**Interfaces:**
- Consumes: `seed_demo_data.run`, the `client`/`db_session_factory` fixtures.

- [ ] **Step 1: Write the test**

```python
# tests/test_synthetic_dataset_matches_e2e.py
"""Workstream 9.c.i's automated counterpart to the live browser
click-through: posts the hero project through the real HTTP API against
the seeded synthetic dataset, and asserts the shortlist is genuinely
differentiated (not everyone scoring ~the same) with the hand-crafted
top match actually on top."""
from app.models.enums import ProjectCategory, StudentBand
from scripts import seed_demo_data

from tests.test_golden_path_e2e import _auth


def _login(client, email: str, password: str) -> str:
    resp = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert resp.status_code == 200, resp.text
    return resp.json()["access_token"]


def test_hero_project_produces_a_differentiated_shortlist_with_expected_top_match(client, db_session_factory):
    db = db_session_factory()
    summary = seed_demo_data.run(db=db)
    db.close()

    business_token = _login(client, summary.hero_business_email, summary.hero_business_password)

    db = db_session_factory()
    from app.models.university import University
    manchester_id = db.query(University.id).filter(University.slug == "manchester").scalar()
    db.close()

    post_resp = client.post(
        "/api/v1/projects",
        headers=_auth(business_token),
        json={
            "title": "Build a customer analytics dashboard",
            "description": (
                "We need an interactive dashboard that visualises customer engagement, retention "
                "and revenue trends from our subscription data, so our team can make faster, "
                "data-informed decisions without waiting on manual reports."
            ),
            "category": ProjectCategory.DATA_ANALYTICS.value,
            "required_skills": ["Python", "SQL", "Data Visualisation", "React"],
            "duration_label": "2-3 weeks",
            "estimated_hours": 20,
            "hourly_rate_gbp": 22,
            "target_university_ids": [manchester_id],
            "target_bands": [StudentBand.YEAR_3.value, StudentBand.YEAR_4_PLUS.value, StudentBand.POSTGRAD_TAUGHT.value],
        },
    )
    assert post_resp.status_code == 201, post_resp.text
    project_id = post_resp.json()["id"]

    shortlist_resp = client.get(f"/api/v1/projects/{project_id}/shortlist", headers=_auth(business_token))
    assert shortlist_resp.status_code == 200, shortlist_resp.text
    entries = shortlist_resp.json()

    assert len(entries) >= 3
    scores = [e["match_score"] for e in entries]
    assert scores == sorted(scores, reverse=True)  # already ranked
    assert scores[0] > scores[-1] + 0.15  # genuinely differentiated, not a flat line

    top_match = entries[0]
    assert top_match["full_name"] == "Priya Anand"
    assert top_match["match_score"] > 0.75

    ella = next(e for e in entries if e["full_name"] == "Ella Marsh")
    assert ella["match_score"] < top_match["match_score"] - 0.15
```

- [ ] **Step 2: Run the test to verify it fails first (before this task existed it would error on import; run it now to confirm current behavior)**

Run: `pytest tests/test_synthetic_dataset_matches_e2e.py -v`
Expected: at this point in the plan every dependency already exists (Tasks 1-9 are done), so this should actually PASS on the first run. If it fails, the failure tells you which earlier task's behavior doesn't line up with this end-to-end expectation — read the assertion that failed and go fix the earlier task, don't weaken this test.

- [ ] **Step 3: Run the full test suite**

Run: `pytest -x -q`
Expected: PASS.

- [ ] **Step 4: Commit**

```bash
git add tests/test_synthetic_dataset_matches_e2e.py
git commit -m "$(cat <<'EOF'
Add e2e test proving the synthetic dataset produces differentiated matches (Workstream 9.c.i)

Posts the exact hero project brief through the real HTTP API against
the seeded dataset and asserts the shortlist is genuinely
differentiated (top vs. bottom match score gap > 0.15) with Priya
Anand — the hand-crafted top-match student — actually ranked first.
This is the automated counterpart to the live browser click-through
in the next task.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

---

## Task 11: Live browser verification of the demo walkthrough

**Files:** none (verification-only task, no code changes).

- [ ] **Step 1: Reseed a clean local dataset**

Run: `python -m scripts.seed_demo_data`
Confirm it prints the hero login and suggested project brief with no errors.

- [ ] **Step 2: Start the app locally**

Run: `uvicorn app.main:app --reload` (or however this project's README says to run it locally — check `caplink/README.md`'s "Running locally" section if unsure of the exact command/port).

- [ ] **Step 3: Load the reference UI and log in as the hero business**

Using `claude-in-chrome` (load the tool if not already loaded: `ToolSearch` with `select:mcp__claude-in-chrome__tabs_context_mcp,mcp__claude-in-chrome__navigate,mcp__claude-in-chrome__computer,mcp__claude-in-chrome__read_page,mcp__claude-in-chrome__tabs_create_mcp,mcp__claude-in-chrome__tabs_close_mcp`), navigate to `/app`, log in with `demo.business@example.com` / `ChangeMe123!`.

- [ ] **Step 4: Post the suggested project through the real UI**

Fill in the "post a project" form with exactly the suggested brief the seed script printed (title, description, category, required skills, duration, hours, rate, target Manchester + the three bands). Submit it.

- [ ] **Step 5: Open the shortlist and confirm the expected story**

Navigate to the new project's shortlist view. Confirm:
- Priya Anand appears at or near the top with a high score (>75%).
- Ella Marsh appears with a visibly lower score than Priya's.
- Clicking "why this match?" (or equivalent) on at least one candidate shows a real factor breakdown, and that the text-similarity factor's detail line says "(semantic match)" for Priya (confirming the embedding path, not the TF-IDF fallback, is actually what's running against real seeded data — not just in a unit test).

- [ ] **Step 6: Note anything that doesn't match expectations**

If the live click-through disagrees with Task 10's automated assertions (e.g. Priya isn't on top, or the semantic-match label doesn't appear), that's a real bug the automated test missed — go back and fix it (likely candidates: `sentence-transformers` not actually installed in the environment the app is running in, or a data mismatch between the seed script and what got typed into the UI form). Do not mark this task done until the live walkthrough genuinely matches what was designed.

- [ ] **Step 7: No commit for this task** — it's verification-only. Move straight to Task 12.

---

## Task 12: Marketing page — "The Secret Sauce (It's Just Maths)"

**Files:**
- Modify: `docs/how-it-works.html`

- [ ] **Step 1: Read the current section this replaces/extends**

Read `docs/how-it-works.html` around its final `<section>` (search for `Matched by relevance, not by who applies first.`) to confirm the exact surrounding markup before editing — it may have shifted slightly since this plan was written.

- [ ] **Step 2: Soften the existing "stays internal" sentence**

Change:
```html
<p>CAPLink matches a student's declared skills, interests and availability against a business's project brief, and factors in a student's reputation from previously completed work. The detail of how that scoring works stays internal — what matters publicly is that it's relevance-based, not a first-come, first-served queue, and that a business always sees why a candidate was suggested to them.</p>
```
to:
```html
<p>CAPLink matches a student's declared skills, interests and availability against a business's project brief, and factors in a student's reputation from previously completed work. We're happy to explain how it thinks — see below — without handing out the exact formula, for the same reason a credit-scoring algorithm doesn't publish its coefficients. What matters publicly is that it's relevance-based, not a first-come, first-served queue, and that a business always sees why a candidate was suggested to them.</p>
```

- [ ] **Step 3: Add the new subsection**

Insert immediately after the `</div>` that closes `.section-head` in that same `<section>`, before its `.cta-row`:

```html
      <div class="sauce" data-reveal>
        <div class="eyebrow">The nerdy bit</div>
        <h3>The Secret Sauce (It's Just Maths)</h3>
        <p>No black box, no mysterious "AI decided" — six plain-English signals, blended and shown to every business as a "why this match?" breakdown. Here's the whole cast:</p>
        <div class="sauce-grid">
          <div class="card sauce-item">
            <strong>Skills overlap</strong>
            <p>Does the student actually have the skills the brief asks for? We're generous about synonyms — "React.js", "reactjs" and "React" all count the same.</p>
          </div>
          <div class="card sauce-item">
            <strong>Semantic fit</strong>
            <p>A small language model reads the project brief and the student's background and asks "do these sound like they belong together?" — the same trick behind modern search, just pointed at a much smaller, friendlier problem.</p>
          </div>
          <div class="card sauce-item">
            <strong>Degree relevance</strong>
            <p>A Data Science degree scores higher against a data project than, say, Fine Art — but adjacent subjects (Economics, Maths) still get real, partial credit. Nobody's shut out for a technicality.</p>
          </div>
          <div class="card sauce-item">
            <strong>Rate &amp; availability fit</strong>
            <p>Simple but essential: is the budget realistic for this student, and do their hours actually add up to the project's timeline?</p>
          </div>
          <div class="card sauce-item">
            <strong>Reputation</strong>
            <p>A statistically-shrunk rating — one 5-star review from a brand-new student doesn't outrank a steady 4.6 average across a dozen completed projects. Small samples don't get to shout the loudest.</p>
          </div>
          <div class="card sauce-item">
            <strong>Collaborative signal</strong>
            <p>Once enough projects have happened, the engine also notices "students like this have done well on projects like that" — quietly learning from the platform's own history, category by category.</p>
          </div>
        </div>
      </div>
```

- [ ] **Step 4: Add the grid layout CSS**

In the `<style>` block near the existing `.card{...}` rule, add:

```css
  .sauce{ margin-top:36px; }
  .sauce h3{ font-size:22px; margin:6px 0 10px; }
  .sauce-grid{ display:grid; grid-template-columns:repeat(3, 1fr); gap:16px; margin-top:20px; }
  .sauce-item p{ margin:8px 0 0; font-size:14px; color:var(--ink-soft); line-height:1.55; }
  @media (max-width:860px){ .sauce-grid{ grid-template-columns:1fr 1fr; } }
  @media (max-width:560px){ .sauce-grid{ grid-template-columns:1fr; } }
```

- [ ] **Step 5: View it in a real browser**

Using `claude-in-chrome`, navigate to `docs/how-it-works.html` (open the file directly, or via whatever local static-file serving this project's README describes) and confirm: the new heading renders, the six cards lay out in a 3-column grid on desktop and stack to 1 column narrow (resize the window to ~400px to check), and the scroll-reveal fade-in still works (the page's existing `data-reveal` JS handles this automatically — no JS changes needed here).

- [ ] **Step 6: Commit**

```bash
git add docs/how-it-works.html
git commit -m "$(cat <<'EOF'
Add "The Secret Sauce (It's Just Maths)" matching explainer (Workstream 9.d.i)

Plain-English, lightly funny walk-through of the six scoring factors
on the public how-it-works page, without publishing exact weights or
the literal formula. Softens the page's prior "stays internal" line so
it doesn't flatly contradict the new section.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

---

## Task 13: Documentation — Workstream 9 in the tracker/plan, and dated CLAUDE.md entries

**Files:**
- Modify: `CAPLink-Technical-Implementation-Plan.docx` (top-level `CAPLink/` folder, not `caplink/`)
- Modify: `CAPLink-Technical-Tracker.xlsx` (same folder)
- Modify: `CLAUDE.md` (top-level)
- Modify: `caplink/CLAUDE.md`

- [ ] **Step 1: Add Workstream 9 to the Technical Implementation Plan docx**

Unzip it (`.docx` is a zip archive) per this project's own established binary-doc convention — see the top-level `CLAUDE.md`'s "Binary docs note" for the exact `zipfile` + `xml.etree.ElementTree` approach already used repeatedly in this project's history (no `python-docx`/`pandoc` available). Add a new "Workstream 9: Demo Realism & Matching Engine Uplift" section, listing all 11 steps from the spec's §3 table (`9.a.i` through `9.d.i`) with their effort/priority, matching the existing workstreams' formatting exactly. Re-zip and overwrite the file. Verify by re-extracting and confirming the new text is present, not just that the zip step didn't error.

- [ ] **Step 2: Add the 11 rows to the Tracker spreadsheet, and recompute the Dashboard**

Follow this project's own established pattern (documented in `caplink/CLAUDE.md`'s "Marketing site build-out + mobile app" entry and its earlier tracker-edit entries — direct XML surgery via `zipfile`/`xml.etree.ElementTree`, no `openpyxl` available): append 11 new rows to the `Tracker` sheet (columns: Step ID, Workstream #=9, Workstream Name, Epic, Step description, Details, Effort, Priority, Status, %-Complete, Owner, Target Date, Notes) with Status set to whatever's actually true at the point this task runs (mark each step "Done" only once its corresponding task above is genuinely complete and verified — if you're running this plan task-by-task rather than all at once, come back and update these rows incrementally rather than writing "Done" for everything up front). Then independently recompute every affected `Dashboard` sheet cell directly from the raw `Tracker` rows (total step count now 115, not 104; Workstream 9's own D/E/F/G/H/I cells; the overall Done/In Progress/Not Started counts; the Priority rollups) — **do not use delta arithmetic against the old cached numbers**, per this project's own standing rule for tracker edits (see the `feedback_tracker_xlsx_editing` memory). Back up the pre-edit file first (`CAPLink-Technical-Tracker.xlsx.backup7` or the next unused backup number).

- [ ] **Step 3: Add a dated entry to `caplink/CLAUDE.md`**

Following this file's own established convention (a new `## <Title> — 2026-09-DD` section near wherever the most recent dated entry currently ends), document: what Workstream 9 actually built (embeddings module + cached columns + swapped scorer factor + synthetic-data generator + hero account + the two verification passes + the marketing subsection), the `ALGORITHM_VERSION` bump to `hybrid_v3`, the new `requirements-ml.txt` gate, and — importantly — the explicit reasoning from the spec that this does not reopen Workstream 4 (link back to the spec file's path so a future session can read the full reasoning rather than it being re-litigated).

- [ ] **Step 4: Update the top-level `CLAUDE.md`'s "Current state"/"Roadmap" sections**

Add Workstream 9 to the roadmap list (it's genuinely new scope beyond the original 104-step plan — say so explicitly, the same way the employer-discovery concept note's status is called out as a deliberate addition rather than silently folded into the original count), and update the "last commit" pointer per this file's own repeated lesson (see its "Current state" header's existing caveat about staleness) to whatever the actual latest commit hash is after Task 12's commit.

- [ ] **Step 5: Verify the docx/xlsx edits actually landed**

Re-extract both files (the same `zipfile` read approach) and confirm the new content is genuinely present — don't trust that a zip-write step succeeded just because it didn't raise an exception.

- [ ] **Step 6: Commit the CLAUDE.md changes** (the `.docx`/`.xlsx` files live in the top-level `CAPLink/` folder, which is **not** a git repo — only the `caplink/CLAUDE.md` change gets committed here; the top-level `CLAUDE.md` and the `.docx`/`.xlsx` files are saved to disk but have no git history to commit to)

```bash
cd caplink
git add CLAUDE.md
git commit -m "$(cat <<'EOF'
Document Workstream 9 (demo realism + matching engine uplift) in CLAUDE.md

Records what actually shipped: the semantic-embedding matching
upgrade (ALGORITHM_VERSION hybrid_v3), the synthetic-data generator
and hero demo account, both verification passes, and the how-it-works
marketing explainer — with an explicit note that this does not reopen
Workstream 4's outcome-based ranking (see the design spec for the
full reasoning).

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

---

## Self-Review Notes

- **Spec coverage:** §3's 11 steps map 1:1 onto Tasks 1-12 (9.a.i→Task 5, 9.a.ii→Tasks 6-8, 9.a.iii→Task 9's hero data, 9.a.iv→Task 9's script wiring, 9.b.i→Task 1, 9.b.ii→Tasks 2-3, 9.b.iii→Task 4, 9.b.iv→tests embedded throughout Tasks 1/4, 9.c.i→Task 10, 9.c.ii→Task 9's idempotency + Task 11's reseed step, 9.d.i→Task 12). §9's risks (deploy weight, model download, honest marketing copy) are called out inline in Task 1's comments and Task 12's constraint.
- **Non-goal guard:** no task here computes anything from `RecommendationLog`/`Application` outcome data — every generator and every scoring change reads only text/skills/degree fields that exist independent of any real usage history, consistent with spec §2.
- **Type/name consistency checked:** `embeddings.refresh_student_embedding`/`refresh_project_embedding` (Task 1) are the exact names re-exported in Task 3 and called in Task 9; `synthetic_data.generate_students/generate_businesses/generate_projects` (Tasks 6-8) are the exact names Task 9's `run()` calls; `SeedSummary`'s four count fields plus `hero_business_email`/`hero_business_password` (Task 9) are the exact fields Task 10's test reads.
