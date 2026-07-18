"""
Skill normalisation + fuzzy matching.

Raw skill strings from student and business input are messy — "React.js" vs
"React" vs "reactjs", "Postgres" vs "PostgreSQL", "ML" vs "Machine Learning".
Naive set-overlap on raw strings misses all of these. This module fixes
that with a synonym table plus a fuzzy-match fallback for near-misses that
aren't in the table (typos, unlisted abbreviations).
"""
import difflib

FUZZY_MATCH_THRESHOLD = 0.8
FUZZY_PARTIAL_CREDIT = 0.7  # a fuzzy (non-exact) match counts for less than an exact one

SKILL_SYNONYMS = {
    "js": "javascript",
    "reactjs": "react",
    "react.js": "react",
    "vuejs": "vue",
    "vue.js": "vue",
    "node": "nodejs",
    "node.js": "nodejs",
    "py": "python",
    "postgres": "postgresql",
    "psql": "postgresql",
    "ml": "machine learning",
    "ai": "artificial intelligence",
    "viz": "data visualisation",
    "dataviz": "data visualisation",
    "data visualization": "data visualisation",
    "stats": "statistics",
    "excel spreadsheets": "excel",
    "ms excel": "excel",
    "figma design": "figma",
    "cx": "customer experience",
    "ux": "user experience",
    "ui": "user interface",
    "seo": "search engine optimisation",
    "gcp": "google cloud platform",
    "aws": "amazon web services",
}


def normalize_skill(skill: str) -> str:
    cleaned = skill.strip().lower()
    return SKILL_SYNONYMS.get(cleaned, cleaned)


def normalized_skill_set(skills: list[str]) -> set[str]:
    return {normalize_skill(s) for s in skills if s.strip()}


def weighted_skill_overlap(student_skills: list[str], required_skills: list[str]) -> tuple[float, list[str]]:
    """
    Returns (score in [0,1], matched_skill_labels).

    Neutral 0.5 when the project didn't specify required skills at all —
    that's a project-authoring gap, not a student mismatch, so it shouldn't
    penalise the student.
    """
    if not required_skills:
        return 0.5, []

    required_norm = [normalize_skill(s) for s in required_skills]
    student_norm = list(normalized_skill_set(student_skills))

    matched_labels: list[str] = []
    credit = 0.0

    for req in required_norm:
        if req in student_norm:
            credit += 1.0
            matched_labels.append(req)
            continue
        best_ratio = max(
            (difflib.SequenceMatcher(None, req, s).ratio() for s in student_norm),
            default=0.0,
        )
        if best_ratio >= FUZZY_MATCH_THRESHOLD:
            credit += FUZZY_PARTIAL_CREDIT
            matched_labels.append(req)

    score = min(credit / len(required_norm), 1.0)
    return score, matched_labels
