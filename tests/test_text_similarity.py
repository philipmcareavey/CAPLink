from app.services.matching.text_similarity import build_idf, cosine_similarity, tokenize


def test_tokenize_strips_stopwords_and_punctuation():
    tokens = tokenize("Analyse the customer churn data, using Python and SQL.")
    assert "the" not in tokens
    assert "and" not in tokens
    assert "python" in tokens
    assert "churn" in tokens


def test_cosine_similarity_identical_text_is_high():
    text = "Customer churn analysis using Python and SQL"
    assert cosine_similarity(text, text) > 0.99


def test_cosine_similarity_unrelated_text_is_low():
    a = "Customer churn analysis using Python and SQL statistics"
    b = "Brand refresh landing page design in Figma"
    assert cosine_similarity(a, b) < 0.2


def test_cosine_similarity_empty_text_returns_zero():
    assert cosine_similarity("", "something") == 0.0
    assert cosine_similarity("something", "") == 0.0


def test_cosine_similarity_partial_overlap_is_between_extremes():
    a = "Customer churn analysis using Python and statistics"
    b = "Market sizing research using Python and economics"
    sim = cosine_similarity(a, b)
    assert 0.0 < sim < 0.99


def test_build_idf_downweights_common_terms():
    corpus = [
        "python data analysis project",
        "python data visualisation project",
        "python data engineering project",
        "brand marketing design project",
    ]
    idf = build_idf(corpus)
    # "python" appears in 3/4 docs, "brand" in 1/4 — brand should be weighted higher (rarer)
    assert idf["brand"] > idf["python"]
