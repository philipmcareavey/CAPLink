from app.models.enums import ProjectCategory, ProjectStatus, StudentBand
from app.models.project import Project
from app.models.user import StudentProfile
from app.services.matching.config import DEFAULT_WEIGHTS
from app.services.matching.scorer import rank_projects_for_student, score_student_against_project


def _make_student(**overrides) -> StudentProfile:
    defaults = dict(
        user_id="student-user-1",
        university_id="uni-1",
        degree_title="BSc Data Science",
        band=StudentBand.YEAR_3,
        modules=["Statistics II", "Machine Learning"],
        skills=["Python", "SQL", "Data Visualisation"],
        portfolio_urls=[],
        hourly_rate_expectation_gbp=19.0,
        weekly_hours_available=10,
        right_to_work_confirmed=True,
        is_id_verified=True,
        average_rating=4.9,
        completed_projects_count=7,
        on_time_rate=0.98,
    )
    defaults.update(overrides)
    return StudentProfile(**defaults)


def _make_project(**overrides) -> Project:
    defaults = dict(
        business_id="biz-1",
        title="Customer Churn Analysis",
        description="Analyse 12 months of subscription data to identify the top churn drivers using Python.",
        category=ProjectCategory.DATA_ANALYTICS,
        required_skills=["Python", "SQL", "Statistics"],
        duration_label="1-2 weeks",
        estimated_hours=15,
        hourly_rate_gbp=19.0,
        is_remote=True,
        target_university_ids=["uni-1"],
        target_bands=[StudentBand.YEAR_3.value],
        status=ProjectStatus.OPEN,
    )
    defaults.update(overrides)
    return Project(**defaults)


def test_strong_match_scores_highly():
    student = _make_student()
    project = _make_project()
    result = score_student_against_project(student, project)
    assert result.score > 0.75
    assert len(result.reasons) > 0


def test_weak_match_scores_lower_than_strong_match():
    student = _make_student()
    strong_project = _make_project()
    weak_project = _make_project(
        title="Brand Refresh Landing Page",
        description="Redesign our marketing landing page in Figma.",
        category=ProjectCategory.DESIGN,
        required_skills=["Figma", "UI Design"],
        hourly_rate_gbp=17.0,
    )

    strong_result = score_student_against_project(student, strong_project)
    weak_result = score_student_against_project(student, weak_project)
    assert strong_result.score > weak_result.score


def test_weights_renormalize_to_approximately_one_without_db():
    student = _make_student()
    project = _make_project()
    result = score_student_against_project(student, project, db=None)
    # Without db, the collaborative factor is entirely absent — remaining
    # factor weights should still sum to ~1.0 after renormalization.
    total_weight = sum(f.weight for f in result.breakdown)
    assert abs(total_weight - 1.0) < 0.01
    assert all(f.name != "collaborative" for f in result.breakdown)


def test_over_budget_student_scores_lower_than_within_budget():
    affordable_student = _make_student(hourly_rate_expectation_gbp=15.0)
    expensive_student = _make_student(hourly_rate_expectation_gbp=45.0)
    project = _make_project(hourly_rate_gbp=18.0)

    affordable_result = score_student_against_project(affordable_student, project)
    expensive_result = score_student_against_project(expensive_student, project)
    assert affordable_result.score > expensive_result.score


def test_rank_projects_for_student_orders_best_match_first():
    student = _make_student()
    strong_project = _make_project()
    weak_project = _make_project(
        title="Brand Refresh Landing Page",
        description="Redesign our marketing landing page in Figma.",
        category=ProjectCategory.DESIGN,
        required_skills=["Figma", "UI Design"],
    )

    ranked = rank_projects_for_student(student, [weak_project, strong_project])
    assert ranked[0][0].title == "Customer Churn Analysis"
    assert ranked[0][1].score >= ranked[1][1].score


def test_reasons_are_human_readable_strings():
    student = _make_student()
    project = _make_project()
    result = score_student_against_project(student, project)
    assert all(isinstance(r, str) and len(r) > 0 for r in result.reasons)


def test_custom_weights_are_respected():
    student = _make_student(hourly_rate_expectation_gbp=45.0)  # badly over budget
    project = _make_project(hourly_rate_gbp=18.0)

    from app.services.matching.config import MatchWeights

    rate_heavy_weights = MatchWeights(
        skill_overlap=0.1, text_similarity=0.0, rate_compatibility=0.7,
        availability=0.1, degree_relevance=0.05, reputation=0.05, collaborative=0.0,
    )
    default_result = score_student_against_project(student, project, weights=DEFAULT_WEIGHTS)
    rate_heavy_result = score_student_against_project(student, project, weights=rate_heavy_weights)
    # Weighting rate compatibility much more heavily should punish the
    # over-budget student harder than the default weighting does.
    assert rate_heavy_result.score < default_result.score
