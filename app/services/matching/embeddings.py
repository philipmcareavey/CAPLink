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
    None (not an exception) if the package isn't installed or the model
    fails to load — the one place this module treats that as an expected,
    valid state rather than an error."""
    try:
        from sentence_transformers import SentenceTransformer
    except ImportError:
        return None
    try:
        return SentenceTransformer(EMBEDDING_MODEL_NAME)
    except Exception:
        return None


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
    # `skills`/`modules` guard against None, not just fall back on falsy —
    # both columns are `default=list`, but a SQLAlchemy column default only
    # applies at flush/INSERT time, not at bare Python construction. Every
    # real write path (auth.py's registration, saml.py's JIT provisioning)
    # calls refresh_student_embedding() on a StudentProfile that hasn't
    # been added to the session yet, so `.skills`/`.modules` are still the
    # Python-level None they start as, not yet `[]` — this project has hit
    # this exact default-timing gap before (see caplink/CLAUDE.md's Epic
    # 2.a entry) and it would otherwise crash `[*None, ...]` with a
    # TypeError on every single registration.
    skills = student.skills or []
    modules = student.modules or []
    return " ".join([*skills, *modules, student.degree_title])


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
