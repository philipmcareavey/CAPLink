from scripts import synthetic_data as sd


def test_degree_pool_has_at_least_fifteen_entries_covering_every_category():
    assert len(sd.DEGREE_POOL) >= 15
    categories_covered = {category for _, category in sd.DEGREE_POOL}
    assert len(categories_covered) >= 5  # a healthy spread, not all piled into one category


def test_skills_by_category_covers_every_degree_pool_category():
    degree_categories = {category for _, category in sd.DEGREE_POOL}
    for category in degree_categories:
        assert category in sd.SKILLS_BY_CATEGORY
        assert len(sd.SKILLS_BY_CATEGORY[category]) >= 3


def test_business_templates_has_eighteen_unique_names_across_every_category():
    assert len(sd.BUSINESS_TEMPLATES) == 18
    names = [b["company_name"] for b in sd.BUSINESS_TEMPLATES]
    assert len(names) == len(set(names))
    categories = {b["category"] for b in sd.BUSINESS_TEMPLATES}
    assert len(categories) >= 5


def test_project_templates_exist_for_every_business_category():
    business_categories = {b["category"] for b in sd.BUSINESS_TEMPLATES}
    for category in business_categories:
        assert category in sd.PROJECT_TEMPLATES_BY_CATEGORY
        assert len(sd.PROJECT_TEMPLATES_BY_CATEGORY[category]) >= 1


def test_unique_email_avoids_collisions():
    used: set[str] = set()
    first = sd.unique_email(None, "Aisha", "Rahman", "manchester.ac.uk", used)
    second = sd.unique_email(None, "Aisha", "Rahman", "manchester.ac.uk", used)
    assert first != second
    assert first in used and second in used
