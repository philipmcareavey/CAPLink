"""
Matching engine — Phase 1 (rules-based) as defined in the implementation
plan. Deliberately simple and fully explainable: every score comes with the
plain-English reasons behind it, which get shown to the user AND stored in
RecommendationLog for training future, smarter versions of this engine.

Swap-in path: once enough RecommendationLog + Application + Rating data
exists, replace `score_student_against_project` internals with a
collaborative-filtering or embedding-based model without touching the
calling code — the function signature is the contract.
"""
from dataclasses import dataclass
from typing import List

from app.models.project import Project
from app.models.user import StudentProfile

SKILL_WEIGHT = 0.5
AVAILABILITY_WEIGHT = 0.2
RATE_WEIGHT = 0.15
DEGREE_RELEVANCE_WEIGHT = 0.15


@dataclass
class MatchResult:
    score: float          # 0.0 - 1.0
    reasons: List[str]


def _skill_overlap_ratio(student_skills: List[str], required_skills: List[str]) -> float:
    if not required_skills:
        return 0.5  # neutral if the project didn't specify
    student_set = {s.lower() for s in student_skills}
    required_set = {s.lower() for s in required_skills}
    if not required_set:
        return 0.5
    overlap = student_set & required_set
    return len(overlap) / len(required_set)


def _rate_compatibility(student_rate: float | None, project_rate: float) -> float:
    if student_rate is None:
        return 0.5
    if student_rate <= project_rate:
        return 1.0
    # Gracefully decay: a student asking 20% over budget still gets partial credit
    overage_ratio = (student_rate - project_rate) / project_rate
    return max(0.0, 1.0 - overage_ratio * 2)


def _availability_score(student_hours: int | None, estimated_hours: int | None) -> float:
    if student_hours is None or estimated_hours is None:
        return 0.5
    return 1.0 if student_hours * 4 >= estimated_hours else 0.6  # rough weekly-vs-total heuristic


def _degree_relevance(student: StudentProfile, project: Project) -> float:
    degree_lower = student.degree_title.lower()
    category_keywords = {
        "data_analytics": ["data", "statistic", "computer", "maths", "mathematics"],
        "software_engineering": ["computer", "software", "engineering"],
        "marketing": ["marketing", "business", "communications"],
        "design": ["design", "art", "media"],
        "research": ["research", "science", "social science", "economics"],
        "finance": ["finance", "economics", "accounting"],
        "operations": ["business", "management", "operations"],
    }
    keywords = category_keywords.get(project.category.value, [])
    return 1.0 if any(k in degree_lower for k in keywords) else 0.3


def score_student_against_project(student: StudentProfile, project: Project) -> MatchResult:
    skill_score = _skill_overlap_ratio(student.skills, project.required_skills)
    rate_score = _rate_compatibility(student.hourly_rate_expectation_gbp, project.hourly_rate_gbp)
    availability_score = _availability_score(student.weekly_hours_available, project.estimated_hours)
    degree_score = _degree_relevance(student, project)

    total = (
        skill_score * SKILL_WEIGHT
        + rate_score * RATE_WEIGHT
        + availability_score * AVAILABILITY_WEIGHT
        + degree_score * DEGREE_RELEVANCE_WEIGHT
    )

    reasons = []
    if skill_score >= 0.5:
        matched = set(s.lower() for s in student.skills) & set(s.lower() for s in project.required_skills)
        if matched:
            reasons.append(f"Skill match: {', '.join(sorted(matched))}")
    if degree_score >= 1.0:
        reasons.append(f"Degree relevance: {student.degree_title}")
    if rate_score >= 1.0:
        reasons.append("Within budget")
    if availability_score >= 1.0:
        reasons.append("Availability fits project hours")
    if student.average_rating >= 4.5 and student.completed_projects_count >= 3:
        reasons.append("Consistently high-rated")
        total = min(1.0, total + 0.05)  # small reputation boost

    if not reasons:
        reasons.append("Partial profile match")

    return MatchResult(score=round(total, 3), reasons=reasons)


def rank_projects_for_student(student: StudentProfile, projects: List[Project]) -> List[tuple[Project, MatchResult]]:
    scored = [(p, score_student_against_project(student, p)) for p in projects]
    scored.sort(key=lambda pair: pair[1].score, reverse=True)
    return scored


def rank_students_for_project(project: Project, students: List[StudentProfile]) -> List[tuple[StudentProfile, MatchResult]]:
    scored = [(s, score_student_against_project(s, project)) for s in students]
    scored.sort(key=lambda pair: pair[1].score, reverse=True)
    return scored
