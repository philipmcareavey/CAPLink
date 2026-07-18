from app.services.matching.skills import normalize_skill, weighted_skill_overlap


def test_normalize_skill_applies_synonyms():
    assert normalize_skill("React.js") == "react"
    assert normalize_skill("JS") == "javascript"
    assert normalize_skill(" Postgres ") == "postgresql"


def test_normalize_skill_passthrough_for_unknown():
    assert normalize_skill("Blender") == "blender"


def test_weighted_skill_overlap_exact_match():
    score, matched = weighted_skill_overlap(["Python", "SQL"], ["python", "sql"])
    assert score == 1.0
    assert set(matched) == {"python", "sql"}


def test_weighted_skill_overlap_synonym_match():
    score, matched = weighted_skill_overlap(["React.js"], ["react"])
    assert score == 1.0


def test_weighted_skill_overlap_fuzzy_typo_partial_credit():
    # "Postgre" is a near-miss typo for "postgresql" — should get partial credit, not zero
    score, matched = weighted_skill_overlap(["Postgre"], ["postgresql"])
    assert 0.0 < score < 1.0


def test_weighted_skill_overlap_no_overlap_scores_low():
    score, matched = weighted_skill_overlap(["Photoshop"], ["python", "sql"])
    assert score == 0.0
    assert matched == []


def test_weighted_skill_overlap_neutral_when_project_specifies_nothing():
    score, matched = weighted_skill_overlap(["Python"], [])
    assert score == 0.5
    assert matched == []


def test_weighted_skill_overlap_partial_match_scores_between_zero_and_one():
    score, _ = weighted_skill_overlap(["Python"], ["python", "sql", "excel"])
    assert 0.0 < score < 1.0
