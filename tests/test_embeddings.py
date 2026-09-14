from app.services.matching import embeddings


def test_embed_text_returns_none_for_empty_text():
    assert embeddings.embed_text("") is None
    assert embeddings.embed_text("   ") is None


def test_embed_text_returns_a_vector_when_model_available():
    if not embeddings.is_available():
        return  # sentence-transformers not installed in this environment — nothing to assert
    vector = embeddings.embed_text("Analyse customer churn using Python and SQL")
    assert vector is not None
    assert len(vector) > 0
    assert all(isinstance(v, float) for v in vector)


def test_similar_sentences_score_higher_than_unrelated_ones():
    if not embeddings.is_available():
        return
    a = embeddings.embed_text("Build an interactive dashboard to visualise customer retention data")
    b = embeddings.embed_text("Create a dashboard showing customer churn and retention trends")
    c = embeddings.embed_text("Design a brand refresh and new logo for a coffee shop")
    assert embeddings.embedding_similarity_score(a, b) > embeddings.embedding_similarity_score(a, c)


def test_cosine_similarity_vectors_handles_mismatched_or_empty_input():
    assert embeddings.cosine_similarity_vectors([], [1.0]) == 0.0
    assert embeddings.cosine_similarity_vectors([1.0, 0.0], [1.0]) == 0.0


def test_embedding_similarity_score_clamps_negative_cosine_to_zero():
    assert embeddings.embedding_similarity_score([1.0, 0.0], [-1.0, 0.0]) == 0.0


def test_student_corpus_text_joins_skills_modules_and_degree():
    class _FakeStudent:
        skills = ["Python", "SQL"]
        modules = ["Statistics II"]
        degree_title = "BSc Data Science"

    text = embeddings.student_corpus_text(_FakeStudent())
    assert text == "Python SQL Statistics II BSc Data Science"


def test_project_corpus_text_joins_title_description_and_required_skills():
    class _FakeProject:
        title = "Churn Analysis"
        description = "Find the top churn drivers."
        required_skills = ["Python", "SQL"]

    text = embeddings.project_corpus_text(_FakeProject())
    assert text == "Churn Analysis Find the top churn drivers. Python SQL"
