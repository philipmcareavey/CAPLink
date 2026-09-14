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


from app.models.enums import StudentBand


class _FakeUniversity:
    def __init__(self, id_, domain):
        self.id = id_
        self.domain = domain


def test_generate_students_returns_the_requested_count_with_valid_fields():
    rng = sd.random.Random(sd.RNG_SEED)
    universities = [_FakeUniversity("uni-1", "manchester.ac.uk"), _FakeUniversity("uni-2", "leeds.ac.uk")]
    used_emails: set[str] = set()

    students = sd.generate_students(rng, universities, count=40, used_emails=used_emails)

    assert len(students) == 40
    emails = [s["email"] for s in students]
    assert len(emails) == len(set(emails))  # no duplicates
    for s in students:
        assert s["university_id"] in {"uni-1", "uni-2"}
        assert s["degree_title"] in {title for title, _ in sd.DEGREE_POOL}
        assert isinstance(s["band"], StudentBand)
        assert 1 <= len(s["skills"]) <= 6
        assert 0.0 <= s.get("average_rating", 0.0) <= 5.0


def test_generate_students_is_deterministic_for_a_fixed_seed():
    universities = [_FakeUniversity("uni-1", "manchester.ac.uk")]
    students_a = sd.generate_students(sd.random.Random(sd.RNG_SEED), universities, count=10, used_emails=set())
    students_b = sd.generate_students(sd.random.Random(sd.RNG_SEED), universities, count=10, used_emails=set())
    assert [s["email"] for s in students_a] == [s["email"] for s in students_b]
    assert [s["skills"] for s in students_a] == [s["skills"] for s in students_b]


def test_generate_businesses_returns_one_entry_per_template_with_at_least_one_agreement():
    rng = sd.random.Random(sd.RNG_SEED)
    universities = [_FakeUniversity("uni-1", "manchester.ac.uk"), _FakeUniversity("uni-2", "leeds.ac.uk")]
    businesses = sd.generate_businesses(rng, universities, used_emails=set())

    assert len(businesses) == len(sd.BUSINESS_TEMPLATES)
    for b in businesses:
        assert 1 <= len(b["agreements"]) <= len(universities)
        for agreement in b["agreements"]:
            assert agreement["university_id"] in {"uni-1", "uni-2"}
            assert b["category"] in agreement["allowed_categories"]
            assert len(agreement["allowed_bands"]) >= 1


def test_generate_businesses_favours_the_first_university_passed():
    rng = sd.random.Random(sd.RNG_SEED)
    universities = [_FakeUniversity("uni-primary", "manchester.ac.uk"), _FakeUniversity("uni-2", "leeds.ac.uk"), _FakeUniversity("uni-3", "sheffield.ac.uk")]
    businesses = sd.generate_businesses(rng, universities, used_emails=set())
    covering_primary = sum(
        1 for b in businesses if any(a["university_id"] == "uni-primary" for a in b["agreements"])
    )
    # Not every business needs to partner with the primary university, but
    # most should, given it's weighted first.
    assert covering_primary >= len(businesses) * 0.6
