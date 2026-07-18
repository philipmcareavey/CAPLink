"""
Lightweight TF-IDF + cosine similarity, pure standard library.

Deliberately not pulling in scikit-learn/numpy for this: the matching
engine needs to run per-request inside a normal API call, on modest text
(a project brief, a student's skill/module list), so a small dependency-free
implementation is both fast enough and one less thing to install/patch.

Usage pattern: build an IDF table once per ranking batch (across all
candidate projects/students being compared in that call) via `build_idf`,
then reuse it across every pairwise `cosine_similarity` call in that batch.
Falls back to pure term-frequency similarity if no IDF table is supplied,
which still works fine for a single one-off comparison.
"""
import math
import re
from collections import Counter

_STOPWORDS = {
    "a", "an", "the", "and", "or", "of", "to", "in", "on", "for", "with",
    "is", "are", "be", "will", "this", "that", "as", "at", "by", "from",
    "we", "you", "your", "our", "it", "its", "into", "using", "use",
}

_TOKEN_RE = re.compile(r"[a-z0-9][a-z0-9+.#-]*")


def tokenize(text: str) -> list[str]:
    if not text:
        return []
    tokens = _TOKEN_RE.findall(text.lower())
    return [t for t in tokens if t not in _STOPWORDS and len(t) > 1]


def build_idf(documents: list[str]) -> dict[str, float]:
    """Standard smoothed IDF: log((1+N)/(1+df)) + 1, so unseen terms still
    get a sane default weight of 1.0 rather than dividing by zero."""
    n_docs = len(documents)
    doc_freq: Counter = Counter()
    for doc in documents:
        doc_freq.update(set(tokenize(doc)))

    idf = {}
    for term, df in doc_freq.items():
        idf[term] = math.log((1 + n_docs) / (1 + df)) + 1.0
    return idf


def _weighted_vector(tokens: list[str], idf: dict[str, float] | None) -> Counter:
    tf = Counter(tokens)
    if idf is None:
        return tf
    return Counter({term: count * idf.get(term, 1.0) for term, count in tf.items()})


def cosine_similarity(text_a: str, text_b: str, idf: dict[str, float] | None = None) -> float:
    tokens_a = tokenize(text_a)
    tokens_b = tokenize(text_b)
    if not tokens_a or not tokens_b:
        return 0.0

    vec_a = _weighted_vector(tokens_a, idf)
    vec_b = _weighted_vector(tokens_b, idf)

    shared_terms = set(vec_a) & set(vec_b)
    dot_product = sum(vec_a[t] * vec_b[t] for t in shared_terms)

    magnitude_a = math.sqrt(sum(v * v for v in vec_a.values()))
    magnitude_b = math.sqrt(sum(v * v for v in vec_b.values()))
    if magnitude_a == 0 or magnitude_b == 0:
        return 0.0

    return dot_product / (magnitude_a * magnitude_b)
