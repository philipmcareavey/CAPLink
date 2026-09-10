"""
Phase-2 collaborative signal, per the implementation plan: "students like
you also succeeded at projects like this." This queries real Application +
StudentProfile history rather than a static table, so it naturally starts
at 0 contribution for brand-new categories and strengthens as real outcome
data accumulates — no special-cased cold-start branch needed, it just falls
out of "no similar accepted applications yet -> no signal".
"""
from typing import Optional

from sqlalchemy.orm import Session

from app.models.application import Application
from app.models.enums import ApplicationStatus
from app.models.project import Project
from app.models.user import StudentProfile
from app.services.matching.skills import normalized_skill_set

MIN_SIMILAR_STUDENTS_FOR_SIGNAL = 2

# (Application, StudentProfile) pairs already accepted for a given category —
# see fetch_accepted_pairs_by_category and collaborative_score's `accepted_pairs`.
AcceptedPairs = list[tuple[Application, StudentProfile]]


def fetch_accepted_pairs_by_category(db: Session, categories) -> dict:
    """One query for every category a batch-ranking call actually needs,
    instead of collaborative_score's own default query running once per
    candidate (Technical Implementation Plan 8.b.ii — profiling
    rank_projects_for_student/rank_students_for_project under realistic
    volume found this as the dominant cost: ~100 candidates sharing ~8
    categories were issuing the same "accepted applications in this
    category" query up to a dozen times over, each also N+1-querying
    StudentProfile per accepted application inside the old collaborative_score.
    Both are fixed by fetching everything this batch could need — Application
    joined straight to its StudentProfile, no per-application follow-up
    query — grouped by category in Python, once, up front."""
    categories = list(set(categories))
    if not categories:
        return {}
    rows = (
        db.query(Application, StudentProfile, Project.category)
        .join(Project, Application.project_id == Project.id)
        .join(StudentProfile, Application.student_id == StudentProfile.id)
        .filter(Project.category.in_(categories), Application.status == ApplicationStatus.ACCEPTED)
        .all()
    )
    by_category: dict = {c: [] for c in categories}
    for application, candidate, category in rows:
        by_category.setdefault(category, []).append((application, candidate))
    return by_category


def collaborative_score(
    db: Session,
    student: StudentProfile,
    project: Project,
    accepted_pairs: Optional[AcceptedPairs] = None,
) -> float | None:
    """
    Returns a 0.0-1.0 score, or None if there isn't enough historical data
    to say anything meaningful yet (caller should exclude this factor and
    renormalize weights across the remaining signals rather than treat
    None as 0 — a genuine "no signal" is different from a genuine "bad fit").

    `accepted_pairs`, if given (see fetch_accepted_pairs_by_category), skips
    this function's own category query entirely — how the batch ranking
    functions avoid re-querying the same category once per candidate.
    Standalone/single-score callers (e.g. the business-side match-explanation
    drill-down, or these tests) leave it out and get the original
    one-query-per-call behaviour, just without the old inner per-application
    StudentProfile lookup either way.
    """
    if accepted_pairs is None:
        rows = (
            db.query(Application, StudentProfile)
            .join(Project, Application.project_id == Project.id)
            .join(StudentProfile, Application.student_id == StudentProfile.id)
            .filter(Project.category == project.category, Application.status == ApplicationStatus.ACCEPTED)
            .all()
        )
        accepted_pairs = [(a, s) for a, s in rows]
    if not accepted_pairs:
        return None

    this_student_skills = normalized_skill_set(student.skills)
    similarity_weighted_ratings: list[tuple[float, float]] = []  # (similarity, rating_out_of_5)

    for application, candidate in accepted_pairs:
        if application.student_id == student.id:
            continue
        if candidate is None or candidate.completed_projects_count == 0:
            continue

        candidate_skills = normalized_skill_set(candidate.skills)
        if not candidate_skills or not this_student_skills:
            continue
        overlap = len(candidate_skills & this_student_skills)
        union = len(candidate_skills | this_student_skills)
        jaccard_similarity = overlap / union if union else 0.0

        if jaccard_similarity > 0:
            similarity_weighted_ratings.append((jaccard_similarity, candidate.average_rating))

    if len(similarity_weighted_ratings) < MIN_SIMILAR_STUDENTS_FOR_SIGNAL:
        return None

    total_weight = sum(sim for sim, _ in similarity_weighted_ratings)
    if total_weight == 0:
        return None

    weighted_avg_rating = sum(sim * rating for sim, rating in similarity_weighted_ratings) / total_weight
    return min(weighted_avg_rating / 5.0, 1.0)
