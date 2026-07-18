from app.services.matching.degree import degree_relevance_score


def test_strong_match_scores_full():
    score, keyword = degree_relevance_score("BSc Data Science", "data_analytics")
    assert score == 1.0
    assert keyword == "data science"


def test_supporting_match_scores_partial():
    score, keyword = degree_relevance_score("BSc Economics", "data_analytics")
    assert score == 0.55
    assert keyword == "economics"


def test_no_match_scores_low_but_not_zero():
    score, keyword = degree_relevance_score("BA Fine Art", "finance")
    assert score == 0.2
    assert keyword is None


def test_strong_beats_supporting_for_overlapping_category():
    strong_score, _ = degree_relevance_score("BSc Computer Science", "software_engineering")
    supporting_score, _ = degree_relevance_score("BEng Electronic Engineering", "software_engineering")
    assert strong_score > supporting_score
