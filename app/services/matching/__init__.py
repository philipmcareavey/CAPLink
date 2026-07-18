"""
CAPLink matching engine — public API.

Other modules should only import from here (`app.services.matching`), not
reach into submodules directly — that keeps this the one stable contract
while the internals (skills.py, text_similarity.py, collaborative.py,
scorer.py) are free to evolve.
"""
from app.services.matching.config import ALGORITHM_VERSION, DEFAULT_WEIGHTS, MatchWeights
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
]
