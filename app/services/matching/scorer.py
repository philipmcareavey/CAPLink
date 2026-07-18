"""
Main scoring orchestration.

Design goals carried over from the implementation plan:
  - Explainable: every score comes with a human-readable "why", not just a number.
  - Swap-in path: rank_projects_for_student / rank_students_for_project /
    score_student_against_project are the stable public contract other
    modules call — internals here can evolve (as they just did, from
    plain weighted-average to this) without touching callers.
  - Graceful degradation: a factor with no data available (e.g. no
    collaborative-filtering signal yet for a new category) is EXCLUDED and
    the remaining weights are renormalized to still sum to 1, rather than
    silently scored as 0 and dragging down every candidate equally.
"""
from dataclasses import dataclass, field
from typing import Optional

from sqlalchemy.orm import Session

from app.models.project import Project
from app.models.user import StudentProfile
from app.services.matching import text_similarity
from app.services.matching.collaborative import collaborative_score
from app.services.matching.config import ALGORITHM_VERSION, DEFAULT_WEIGHTS, MatchWeights
from app.services.matching.degree import degree_relevance_score
from app.services.matching.reputation import availability_score, rate_compatibility_score, reputation_score
from app.services.matching.skills import weighted_skill_overlap


@dataclass
class ScoreFactor:
    name: str
    raw_score: float          # 0-1, before weighting
    weight: float              # the (possibly renormalized) weight actually applied
    contribution: float        # raw_score * weight
    detail: str                # human-readable explanation of this specific factor


@dataclass
class MatchResult:
    score: float                        # 0-1 overall
    reasons: list[str]                  # top human-readable reasons, for UI chips
    breakdown: list[ScoreFactor] = field(default_factory=list)   # full explainability detail
    algorithm_version: str = ALGORITHM_VERSION


def _student_corpus_text(student: StudentProfile) -> str:
    return " ".join([*student.skills, *student.modules, student.degree_title])


def _project_corpus_text(project: Project) -> str:
    return " ".join([project.title, project.description, *project.required_skills])


def score_student_against_project(
    student: StudentProfile,
    project: Project,
    db: Optional[Session] = None,
    idf: Optional[dict[str, float]] = None,
    weights: MatchWeights = DEFAULT_WEIGHTS,
) -> MatchResult:
    """
    Score one student against one project.

    `db` is optional: pass it to enable the collaborative-filtering factor
    (requires querying real application/rating history). Without it, that
    factor is simply excluded and its weight redistributed — the function
    still works standalone (e.g. in a unit test) with no database at all.
    """
    factors: list[ScoreFactor] = []
    weight_map = weights.as_dict()

    # --- Skill overlap ---
    skill_raw, matched_skills = weighted_skill_overlap(student.skills, project.required_skills)
    factors.append(ScoreFactor(
        "skill_overlap", skill_raw, weight_map["skill_overlap"], 0.0,
        f"Matched skills: {', '.join(matched_skills)}" if matched_skills else "No direct skill overlap",
    ))

    # --- Free-text similarity (project brief vs student's declared background) ---
    text_raw = text_similarity.cosine_similarity(_project_corpus_text(project), _student_corpus_text(student), idf)
    factors.append(ScoreFactor(
        "text_similarity", text_raw, weight_map["text_similarity"], 0.0,
        "Project brief closely matches student's background" if text_raw >= 0.35 else "Limited textual overlap",
    ))

    # --- Rate compatibility ---
    rate_raw = rate_compatibility_score(student.hourly_rate_expectation_gbp, project.hourly_rate_gbp)
    factors.append(ScoreFactor(
        "rate_compatibility", rate_raw, weight_map["rate_compatibility"], 0.0,
        "Within budget" if rate_raw >= 1.0 else "Above budget",
    ))

    # --- Availability ---
    avail_raw = availability_score(student.weekly_hours_available, project.estimated_hours)
    factors.append(ScoreFactor(
        "availability", avail_raw, weight_map["availability"], 0.0,
        "Availability comfortably fits project timeframe" if avail_raw >= 1.0 else "Tight or unclear availability fit",
    ))

    # --- Degree relevance ---
    degree_raw, matched_keyword = degree_relevance_score(student.degree_title, project.category.value)
    factors.append(ScoreFactor(
        "degree_relevance", degree_raw, weight_map["degree_relevance"], 0.0,
        f"Degree relevance: {student.degree_title}" if degree_raw >= 1.0
        else (f"Adjacent degree relevance ({matched_keyword})" if matched_keyword else "No clear degree relevance"),
    ))

    # --- Reputation (Bayesian-shrunk) ---
    reputation_raw = reputation_score(student.average_rating, student.completed_projects_count)
    factors.append(ScoreFactor(
        "reputation", reputation_raw, weight_map["reputation"], 0.0,
        f"Track record: {student.average_rating:.1f}★ across {student.completed_projects_count} projects"
        if student.completed_projects_count > 0 else "No completed projects yet",
    ))

    # --- Collaborative filtering (optional — needs db + historical data) ---
    if db is not None:
        collab_raw = collaborative_score(db, student, project)
        if collab_raw is not None:
            factors.append(ScoreFactor(
                "collaborative", collab_raw, weight_map["collaborative"], 0.0,
                "Students with a similar profile have performed well on similar projects"
                if collab_raw >= 0.7 else "Mixed outcomes for similar students on similar projects",
            ))
        # else: no signal yet for this category — factor omitted entirely, not zeroed.

    # --- Dynamic renormalization: only factors actually present get weight ---
    total_active_weight = sum(f.weight for f in factors)
    if total_active_weight == 0:
        total_active_weight = 1.0  # defensive; shouldn't happen given always-present factors

    overall_score = 0.0
    for f in factors:
        normalized_weight = f.weight / total_active_weight
        f.weight = round(normalized_weight, 4)
        f.contribution = round(f.raw_score * normalized_weight, 4)
        overall_score += f.contribution

    # --- Reason chips: surface the top contributing, meaningfully-positive factors ---
    positive_factors = sorted(
        (f for f in factors if f.raw_score >= 0.6 and f.contribution > 0),
        key=lambda f: f.contribution,
        reverse=True,
    )
    reasons = [f.detail for f in positive_factors[:4]]
    if not reasons:
        reasons = ["Partial profile match"]

    return MatchResult(score=round(min(overall_score, 1.0), 3), reasons=reasons, breakdown=factors)


def rank_projects_for_student(
    student: StudentProfile,
    projects: list[Project],
    db: Optional[Session] = None,
    weights: MatchWeights = DEFAULT_WEIGHTS,
) -> list[tuple[Project, MatchResult]]:
    """Batch-scores and ranks projects for one student. Builds a shared IDF
    table across the candidate batch so text_similarity reflects how
    distinctive a term is within THIS set of projects, not just raw overlap."""
    corpus = [_project_corpus_text(p) for p in projects] + [_student_corpus_text(student)]
    idf = text_similarity.build_idf(corpus)

    scored = [
        (project, score_student_against_project(student, project, db=db, idf=idf, weights=weights))
        for project in projects
    ]
    scored.sort(key=lambda pair: pair[1].score, reverse=True)
    return scored


def rank_students_for_project(
    project: Project,
    students: list[StudentProfile],
    db: Optional[Session] = None,
    weights: MatchWeights = DEFAULT_WEIGHTS,
) -> list[tuple[StudentProfile, MatchResult]]:
    corpus = [_student_corpus_text(s) for s in students] + [_project_corpus_text(project)]
    idf = text_similarity.build_idf(corpus)

    scored = [
        (student, score_student_against_project(student, project, db=db, idf=idf, weights=weights))
        for student in students
    ]
    scored.sort(key=lambda pair: pair[1].score, reverse=True)
    return scored
