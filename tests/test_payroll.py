from app.models.contract import Contract, Milestone
from app.models.enums import PaymentRail, StudentBand, UserRole
from app.models.university import University
from app.models.user import StudentProfile, User
from app.services.payroll import (
    LoggingPayrollProvider,
    determine_payment_rail,
    export_payroll_csv,
    submit_payroll_batch,
)


def _make_student(db_session, visa_weekly_hour_cap=None):
    university = University(name="Test Uni", slug="test-uni-payroll", domain="test-payroll.ac.uk")
    db_session.add(university)
    db_session.flush()
    user = User(
        email="student@test-payroll.ac.uk", hashed_password="x", role=UserRole.STUDENT,
        full_name="Student", is_email_verified=True, university_id=university.id,
    )
    db_session.add(user)
    db_session.flush()
    student = StudentProfile(
        user_id=user.id, university_id=university.id, degree_title="CS", band=StudentBand.YEAR_2,
        visa_weekly_hour_cap=visa_weekly_hour_cap,
    )
    db_session.add(student)
    db_session.flush()
    return student


def test_determine_payment_rail_self_employed_by_default(db_session):
    student = _make_student(db_session, visa_weekly_hour_cap=None)
    assert determine_payment_rail(student) == PaymentRail.SELF_EMPLOYED


def test_determine_payment_rail_forces_paye_for_visa_restricted_student(db_session):
    student = _make_student(db_session, visa_weekly_hour_cap=20)
    assert determine_payment_rail(student) == PaymentRail.PAYE_UMBRELLA


def test_export_payroll_csv_contains_expected_columns_and_rows(db_session):
    student = _make_student(db_session, visa_weekly_hour_cap=20)
    contract = Contract(
        project_id="proj-1", application_id="app-1", student_id=student.id, business_id="biz-1",
        payment_rail=PaymentRail.PAYE_UMBRELLA,
    )
    db_session.add(contract)
    db_session.flush()
    milestone = Milestone(contract_id=contract.id, description="Build the thing", payment_amount_gbp=150.0)
    db_session.add(milestone)
    db_session.flush()

    csv_text = export_payroll_csv([(milestone, contract, student)])
    assert "project_reference,student_full_name,student_email,milestone_description,amount_gbp" in csv_text
    assert "Build the thing" in csv_text
    assert "150.0" in csv_text
    assert student.user.email in csv_text


def test_submit_payroll_batch_marks_milestones_exported(db_session):
    student = _make_student(db_session, visa_weekly_hour_cap=20)
    contract = Contract(
        project_id="proj-1", application_id="app-1", student_id=student.id, business_id="biz-1",
        payment_rail=PaymentRail.PAYE_UMBRELLA,
    )
    db_session.add(contract)
    db_session.flush()
    milestone = Milestone(contract_id=contract.id, description="Build the thing", payment_amount_gbp=150.0)
    db_session.add(milestone)
    db_session.flush()

    assert milestone.payroll_exported_at is None
    submit_payroll_batch([(milestone, contract, student)], LoggingPayrollProvider())
    assert milestone.payroll_exported_at is not None
