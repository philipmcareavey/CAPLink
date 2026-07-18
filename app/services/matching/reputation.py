"""
Small, independently-testable sub-scorers that don't warrant their own
module but shouldn't be buried inline in scorer.py either.
"""
from app.services.matching.config import REPUTATION_PRIOR_SCORE, REPUTATION_PRIOR_WEIGHT


def reputation_score(average_rating: float, completed_projects_count: int) -> float:
    """
    Bayesian-shrunk reputation, 0-1. A student with one 5-star rating and a
    student with twenty 4.8-star ratings should NOT score the same — the
    shrinkage pulls low-volume ratings toward a neutral prior so a single
    lucky (or unlucky) review can't dominate the score early in a student's
    history. As completed_projects_count grows, the shrinkage relaxes and
    the student's actual average dominates, as it should.
    """
    if completed_projects_count <= 0:
        return REPUTATION_PRIOR_SCORE / 5.0

    shrunk = (
        average_rating * completed_projects_count + REPUTATION_PRIOR_SCORE * REPUTATION_PRIOR_WEIGHT
    ) / (completed_projects_count + REPUTATION_PRIOR_WEIGHT)
    return min(shrunk / 5.0, 1.0)


def rate_compatibility_score(student_expected_rate: float | None, project_rate: float) -> float:
    """1.0 if the student would accept at/under budget; graceful decay above it
    rather than a hard cutoff, since a slightly-over-budget great match is
    still worth surfacing (the business can negotiate)."""
    if student_expected_rate is None or project_rate <= 0:
        return 0.5
    if student_expected_rate <= project_rate:
        return 1.0
    overage_ratio = (student_expected_rate - project_rate) / project_rate
    return max(0.0, 1.0 - overage_ratio * 2)


def availability_score(student_weekly_hours: int | None, project_estimated_hours: int | None) -> float:
    """
    Rough but sane heuristic: can the student plausibly finish the project
    within ~4 working weeks given their stated weekly availability? Full
    credit if comfortably so, partial credit if tight-but-feasible, low
    credit if it would take an unreasonably long time.
    """
    if student_weekly_hours is None or project_estimated_hours is None or student_weekly_hours <= 0:
        return 0.5
    weeks_needed = project_estimated_hours / student_weekly_hours
    if weeks_needed <= 3:
        return 1.0
    if weeks_needed <= 6:
        return 0.7
    if weeks_needed <= 10:
        return 0.4
    return 0.15
