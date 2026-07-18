"""
Phase-2 collaborative signal, per the implementation plan: "students like
you also succeeded at projects like this." This queries real Application +
StudentProfile history rather than a static table, so it naturally starts
at 0 contribution for brand-new categories and strengthens as real outcome
data accumulates — no special-cased cold-start branch needed, it just falls
out of "no similar accepted applications yet -> no signal".
"""
from sqlalchemy.orm import Session

from app.models.application import Application
from app.models.enums import ApplicationStatus
from app.models.project import Project
from app.models.user import StudentProfile
from app.services.matching.skills import normalized_skill_set

MIN_SIMILAR_STUDENTS_FOR_SIGNAL = 2


def collaborative_score(db: Session, student: StudentProfile, project: Project) -> float | None:
    """
    Returns a 0.0-1.0 score, or None if there isn't enough historical data
    to say anything meaningful yet (caller should exclude this factor and
    renormalize weights across the remaining signals rather than treat
    None as 0 — a genuine "no signal" is different from a genuine "bad fit").
    """
    accepted_in_category = (
        db.query(Application)
        .join(Project, Application.project_id == Project.id)
        .filter(Project.category == project.category, Application.status == ApplicationStatus.ACCEPTED)
        .all()
    )
    if not accepted_in_category:
        return None

    this_student_skills = normalized_skill_set(student.skills)
    similarity_weighted_ratings: list[tuple[float, float]] = []  # (similarity, rating_out_of_5)

    for application in accepted_in_category:
        if application.student_id == student.id:
            continue
        candidate = db.query(StudentProfile).filter(StudentProfile.id == application.student_id).first()
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
