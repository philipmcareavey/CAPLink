"""
Tunable configuration for the matching engine. Pulling these out into one
place means a platform admin (or, later, an auto-tuning job that reads
RecommendationLog outcomes) can adjust engine behaviour without touching
scoring logic.
"""
from dataclasses import dataclass, fields


@dataclass(frozen=True)
class MatchWeights:
    """
    Relative importance of each signal, 0-1, nominally summing to 1.0.
    Not every signal is available for every score (e.g. collaborative data
    may not exist yet for a brand-new category) — see scorer.py's dynamic
    renormalization, which redistributes an unavailable factor's weight
    across the remaining active factors rather than silently zeroing it out.
    """
    skill_overlap: float = 0.32
    text_similarity: float = 0.14
    rate_compatibility: float = 0.12
    availability: float = 0.12
    degree_relevance: float = 0.12
    reputation: float = 0.10
    collaborative: float = 0.08

    def as_dict(self) -> dict:
        return {f.name: getattr(self, f.name) for f in fields(self)}


DEFAULT_WEIGHTS = MatchWeights()

# Bumped from rules_v2 to hybrid_v3: the text_similarity factor now prefers
# a cached semantic-embedding score over TF-IDF cosine similarity whenever
# both sides of a comparison have one (Workstream 9.b) — every other
# factor and the overall weighting scheme is unchanged.
#
# KNOWN LIMITATION, deliberately not fixed here: this one string is written
# to every RecommendationLog row regardless of which mechanism actually
# produced that score. "hybrid_v3" means "the engine is capable of the
# embedding path", NOT "this row used it" — a row scored entirely on the
# TF-IDF fallback (sentence-transformers not installed, or either side
# missing a cached vector — the normal case on staging/Docker/CI today,
# see README's "Optional semantic-embedding dependency") is logged
# identically to one scored on real embeddings. So `algorithm_version`
# cannot be used to segment logged recommendations by scoring mechanism.
# A future workstream that needs that distinction (e.g. measuring whether
# embeddings actually improve hire rates) should add a separate field to
# RecommendationLog — e.g. `text_similarity_method` — rather than
# overloading this version string with two orthogonal meanings.
ALGORITHM_VERSION = "hybrid_v3"

# Keywords used for degree/module <-> project category relevance. Expanded
# vs. the original single-word list, and split into "strong" (title-level
# discipline match) vs "supporting" (adjacent discipline, partial credit).
CATEGORY_KEYWORDS: dict[str, dict[str, list[str]]] = {
    "data_analytics": {
        "strong": ["data science", "data analytics", "statistics", "computer science"],
        "supporting": ["mathematics", "maths", "economics", "physics", "engineering"],
    },
    "software_engineering": {
        "strong": ["computer science", "software engineering", "computing"],
        "supporting": ["mathematics", "electronic engineering", "data science"],
    },
    "marketing": {
        "strong": ["marketing", "communications", "media studies"],
        "supporting": ["business", "management", "psychology"],
    },
    "design": {
        "strong": ["design", "graphic design", "art", "media production"],
        "supporting": ["architecture", "marketing", "computer science"],
    },
    "research": {
        "strong": ["research methods", "social science", "science"],
        "supporting": ["economics", "psychology", "politics", "data science"],
    },
    "finance": {
        "strong": ["finance", "accounting", "economics"],
        "supporting": ["business", "management", "mathematics"],
    },
    "operations": {
        "strong": ["business", "management", "operations"],
        "supporting": ["logistics", "economics", "engineering"],
    },
    "other": {"strong": [], "supporting": []},
}

# Bayesian shrinkage prior for reputation scoring — prevents a single 5-star
# rating from one project outweighing a track record of many good-but-not-
# perfect ones. See scorer._reputation_score for the formula.
REPUTATION_PRIOR_SCORE = 3.6   # out of 5 — a plausible "unknown student" baseline
REPUTATION_PRIOR_WEIGHT = 3    # equivalent to ~3 "phantom" average ratings
