from app.services.matching.reputation import availability_score, rate_compatibility_score, reputation_score


def test_reputation_score_new_student_gets_neutral_prior():
    score = reputation_score(average_rating=0.0, completed_projects_count=0)
    assert 0.6 < score < 0.8  # prior of 3.6/5 = 0.72


def test_reputation_score_single_five_star_is_shrunk_toward_prior():
    single_review = reputation_score(average_rating=5.0, completed_projects_count=1)
    veteran = reputation_score(average_rating=4.8, completed_projects_count=20)
    # A lone 5-star shouldn't outscore a strong, well-established track record
    assert single_review < veteran


def test_reputation_score_shrinkage_relaxes_with_volume():
    low_volume = reputation_score(average_rating=5.0, completed_projects_count=1)
    high_volume = reputation_score(average_rating=5.0, completed_projects_count=25)
    # Both are 5.0 average, but more volume means the shrinkage pulls less —
    # so high_volume should sit closer to the true 1.0 ceiling.
    assert high_volume > low_volume


def test_rate_compatibility_within_budget_is_full_score():
    assert rate_compatibility_score(15.0, 20.0) == 1.0
    assert rate_compatibility_score(20.0, 20.0) == 1.0


def test_rate_compatibility_over_budget_decays_gracefully():
    slightly_over = rate_compatibility_score(22.0, 20.0)
    way_over = rate_compatibility_score(40.0, 20.0)
    assert 0.0 < slightly_over < 1.0
    assert way_over < slightly_over


def test_rate_compatibility_unknown_expectation_is_neutral():
    assert rate_compatibility_score(None, 20.0) == 0.5


def test_availability_score_comfortable_fit():
    # 10 hrs/week, 15 total hours needed -> 1.5 weeks, comfortably under 3
    assert availability_score(10, 15) == 1.0


def test_availability_score_tight_fit_scores_lower():
    # 2 hrs/week, 15 total hours -> 7.5 weeks -> "tight but feasible" band
    score = availability_score(2, 15)
    assert 0.0 < score < 1.0


def test_availability_score_unknown_is_neutral():
    assert availability_score(None, 15) == 0.5
    assert availability_score(10, None) == 0.5
