from app.models.enums import ProjectCategory, ProjectStatus, StudentBand
from app.models.project import Project
from app.models.user import StudentProfile
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


def test_load_model_gracefully_degrades_when_model_construction_fails(monkeypatch):
    """Verify that _load_model() returns None when SentenceTransformer
    construction fails, not just when the package is missing."""
    # Clear the cache to force a fresh load attempt
    embeddings._load_model.cache_clear()

    # Mock SentenceTransformer to raise an exception on construction
    class FailingSentenceTransformer:
        def __init__(self, *args, **kwargs):
            raise OSError("Model download failed: no network available")

    # Monkeypatch the import within the embeddings module
    import sys
    original_module = sys.modules.get("sentence_transformers")
    try:
        mock_module = type(sys)("sentence_transformers")
        mock_module.SentenceTransformer = FailingSentenceTransformer
        sys.modules["sentence_transformers"] = mock_module

        # Call _load_model - should not raise, should return None
        result = embeddings._load_model()
        assert result is None

        # Verify is_available() also returns False
        assert embeddings.is_available() is False

        # Verify embed_text() returns None gracefully
        assert embeddings.embed_text("test text") is None

    finally:
        # Restore the original module
        embeddings._load_model.cache_clear()
        if original_module is not None:
            sys.modules["sentence_transformers"] = original_module
        elif "sentence_transformers" in sys.modules:
            del sys.modules["sentence_transformers"]


def test_student_profile_and_project_have_a_nullable_embedding_column():
    student = StudentProfile(
        user_id="u1", university_id="uni-1", degree_title="BSc Data Science", band=StudentBand.YEAR_3,
    )
    project = Project(
        business_id="biz-1", title="t", description="d", category=ProjectCategory.DATA_ANALYTICS,
        duration_label="1 week", hourly_rate_gbp=20, status=ProjectStatus.OPEN,
    )
    assert student.embedding is None
    assert project.embedding is None
    student.embedding = [0.1, 0.2]
    project.embedding = [0.3, 0.4]
    assert student.embedding == [0.1, 0.2]
    assert project.embedding == [0.3, 0.4]
