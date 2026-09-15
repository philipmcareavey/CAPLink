"""The text_similarity factor can be scored two ways — semantic-embedding
cosine similarity or the original TF-IDF word-overlap cosine — and the two
are NOT on a comparable scale (related text lands ~0.3-0.6 under
embeddings; TF-IDF over short skill lists clusters near 0 or near 1).

Mixing them inside a single ranked list would sort candidates against two
different yardsticks with nothing telling the caller which won which
comparison. So the choice is made once per batch by
scorer._batch_uses_embeddings, not per pair. These tests pin that:
an all-embedded batch uses embeddings for everyone, and a batch where even
one candidate lacks an embedding drops to TF-IDF for EVERYONE, not just
that one candidate.

Embeddings here are hand-written unit vectors, not real model output — the
point under test is which code path a batch chooses, which must hold
identically whether or not sentence-transformers is installed.
"""
from app.services.matching.scorer import rank_projects_for_student, rank_students_for_project
from tests.test_scorer import _make_project, _make_student

# Hand-built unit vectors. Exact values are irrelevant to these tests —
# only presence/absence of an embedding decides the path.
_VEC_A = [1.0, 0.0, 0.0]
_VEC_B = [0.8, 0.6, 0.0]
_VEC_C = [0.0, 1.0, 0.0]

# scorer.py words the two paths' explanations differently on purpose; that
# wording is the observable signal for which path actually ran.
_SEMANTIC_MARKER = "semantic"


def _text_details(scored) -> list[str]:
    details = []
    for _candidate, result in scored:
        factor = next(f for f in result.breakdown if f.name == "text_similarity")
        details.append(factor.detail)
    return details


def test_batch_with_every_candidate_embedded_uses_the_embedding_path_for_all():
    student = _make_student(user_id="s-all", embedding=_VEC_A)
    projects = [
        _make_project(title="Churn Analysis", embedding=_VEC_B),
        _make_project(title="Sales Dashboard", embedding=_VEC_C),
        _make_project(title="Retention Report", embedding=_VEC_A),
    ]

    details = _text_details(rank_projects_for_student(student, projects))

    assert len(details) == 3
    assert all(_SEMANTIC_MARKER in d for d in details), details


def test_one_unembedded_candidate_drops_the_whole_batch_to_tfidf():
    student = _make_student(user_id="s-mixed", embedding=_VEC_A)
    projects = [
        _make_project(title="Churn Analysis", embedding=_VEC_B),
        _make_project(title="Sales Dashboard", embedding=None),  # the odd one out
        _make_project(title="Retention Report", embedding=_VEC_A),
    ]

    details = _text_details(rank_projects_for_student(student, projects))

    assert len(details) == 3
    # Not "two semantic, one TF-IDF" — all three must share one scale.
    assert not any(_SEMANTIC_MARKER in d for d in details), details


def test_student_side_batch_with_every_candidate_embedded_uses_embeddings_for_all():
    project = _make_project(embedding=_VEC_A)
    students = [
        _make_student(user_id="s-1", embedding=_VEC_B),
        _make_student(user_id="s-2", embedding=_VEC_C),
        _make_student(user_id="s-3", embedding=_VEC_A),
    ]

    details = _text_details(rank_students_for_project(project, students))

    assert len(details) == 3
    assert all(_SEMANTIC_MARKER in d for d in details), details


def test_student_side_batch_falls_back_wholesale_when_one_student_lacks_an_embedding():
    project = _make_project(embedding=_VEC_A)
    students = [
        _make_student(user_id="s-1", embedding=_VEC_B),
        _make_student(user_id="s-2", embedding=None),  # the odd one out
        _make_student(user_id="s-3", embedding=_VEC_A),
    ]

    details = _text_details(rank_students_for_project(project, students))

    assert len(details) == 3
    assert not any(_SEMANTIC_MARKER in d for d in details), details


def test_student_side_batch_falls_back_when_the_project_itself_lacks_an_embedding():
    """The shared side of the batch counts too — an unembedded project can't
    be compared semantically against anyone, however well-embedded they are."""
    project = _make_project(embedding=None)
    students = [
        _make_student(user_id="s-1", embedding=_VEC_B),
        _make_student(user_id="s-2", embedding=_VEC_C),
    ]

    details = _text_details(rank_students_for_project(project, students))

    assert not any(_SEMANTIC_MARKER in d for d in details), details


def test_single_score_call_still_decides_per_pair():
    """The public per-pair contract is unchanged: a standalone
    score_student_against_project (e.g. the business-side match-explanation
    drill-down) has no batch to be consistent with, so it uses embeddings
    whenever both sides happen to have one."""
    from app.services.matching.scorer import score_student_against_project

    embedded = score_student_against_project(
        _make_student(embedding=_VEC_A), _make_project(embedding=_VEC_B),
    )
    detail = next(f for f in embedded.breakdown if f.name == "text_similarity").detail
    assert _SEMANTIC_MARKER in detail

    unembedded = score_student_against_project(
        _make_student(embedding=_VEC_A), _make_project(embedding=None),
    )
    detail = next(f for f in unembedded.breakdown if f.name == "text_similarity").detail
    assert _SEMANTIC_MARKER not in detail
