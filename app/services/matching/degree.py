from app.services.matching.config import CATEGORY_KEYWORDS


def degree_relevance_score(degree_title: str, category_value: str) -> tuple[float, str | None]:
    """
    Returns (score in [0,1], matched_keyword_or_None).
    Strong match (e.g. 'BSc Data Science' vs data_analytics) scores 1.0.
    Supporting/adjacent match (e.g. 'BSc Economics' vs data_analytics)
    scores 0.55 — relevant, but the plain rules_v1 engine treated this
    identically to a non-match, which under-served econ/maths/physics
    students who are frequently strong candidates for data-adjacent work.
    No match at all scores 0.2, not 0 — a project brief rarely requires a
    literal matching degree title, so we don't want to zero out otherwise
    strong candidates purely on a keyword miss.
    """
    keywords = CATEGORY_KEYWORDS.get(category_value, {"strong": [], "supporting": []})
    degree_lower = degree_title.lower()

    for kw in keywords["strong"]:
        if kw in degree_lower:
            return 1.0, kw
    for kw in keywords["supporting"]:
        if kw in degree_lower:
            return 0.55, kw
    return 0.2, None
