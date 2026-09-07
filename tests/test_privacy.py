from app.models.contract import Contract, Milestone
from app.models.device import Device
from app.models.enums import DevicePlatform, PaymentRail, StudentBand, UserRole
from app.models.message import Message, MessageThread
from app.models.rating import Rating
from app.models.university import University
from app.models.user import BusinessProfile, StudentProfile, User
from app.services.privacy import anonymize_user_account, export_user_data


def _make_student_with_data(db_session):
    university = University(name="Test Uni", slug="test-uni-privacy", domain="test-privacy.ac.uk")
    db_session.add(university)
    db_session.flush()

    student_user = User(
        email="student@test-privacy.ac.uk", hashed_password="x", role=UserRole.STUDENT,
        full_name="Priva Cy", is_email_verified=True, university_id=university.id,
    )
    biz_user = User(
        email="biz@test-privacy.com", hashed_password="x", role=UserRole.BUSINESS,
        full_name="Biz Contact", is_email_verified=True,
    )
    db_session.add_all([student_user, biz_user])
    db_session.flush()

    student = StudentProfile(
        user_id=student_user.id, university_id=university.id, degree_title="CS", band=StudentBand.YEAR_2,
        portfolio_urls=["https://priva.cy/portfolio"], skills=["Python"],
    )
    business = BusinessProfile(user_id=biz_user.id, company_name="Acme")
    db_session.add_all([student, business])
    db_session.flush()

    device = Device(user_id=student_user.id, platform=DevicePlatform.WEB, push_token="tok-123")
    db_session.add(device)

    contract = Contract(
        project_id="p1", application_id="a1", student_id=student.id, business_id=business.id,
        payment_rail=PaymentRail.SELF_EMPLOYED,
    )
    db_session.add(contract)
    db_session.flush()
    milestone = Milestone(contract_id=contract.id, description="Do work", payment_amount_gbp=50.0)
    db_session.add(milestone)

    thread = MessageThread(project_id=None, student_user_id=student_user.id, business_user_id=biz_user.id)
    db_session.add(thread)
    db_session.flush()
    message = Message(thread_id=thread.id, sender_user_id=student_user.id, content="Hello there")
    db_session.add(message)

    rating = Rating(contract_id=contract.id, rater_user_id=student_user.id, ratee_user_id=biz_user.id, overall_score=5.0)
    db_session.add(rating)
    db_session.commit()

    return student_user, student, biz_user, business


def test_export_user_data_includes_everything(db_session):
    student_user, student, biz_user, business = _make_student_with_data(db_session)

    data = export_user_data(db_session, student_user)

    assert data["account"]["email"] == "student@test-privacy.ac.uk"
    assert data["student_profile"]["degree_title"] == "CS"
    assert len(data["contracts"]) == 1
    assert data["contracts"][0]["milestones"][0]["description"] == "Do work"
    assert len(data["messages"]) == 1
    assert data["messages"][0]["content"] == "Hello there"
    assert data["messages"][0]["sent_by_you"] is True
    assert len(data["ratings_given"]) == 1
    assert len(data["devices"]) == 1


def test_export_includes_received_messages_and_ratings_too(db_session):
    student_user, student, biz_user, business = _make_student_with_data(db_session)

    biz_data = export_user_data(db_session, biz_user)
    assert len(biz_data["messages"]) == 1  # the business receives the student's message too
    assert biz_data["messages"][0]["sent_by_you"] is False
    assert len(biz_data["ratings_received"]) == 1


def test_anonymize_clears_identifying_fields_but_keeps_structural_rows(db_session):
    student_user, student, biz_user, business = _make_student_with_data(db_session)
    student_user_id = student_user.id

    anonymize_user_account(db_session, student_user)
    db_session.commit()

    refreshed = db_session.query(User).filter(User.id == student_user_id).first()
    assert refreshed.email == f"deleted-user-{student_user_id}@deleted.caplink.invalid"
    assert refreshed.full_name == "Deleted User"
    assert refreshed.is_active is False
    assert refreshed.deleted_at is not None

    refreshed_student = db_session.query(StudentProfile).filter(StudentProfile.user_id == student_user_id).first()
    assert refreshed_student.portfolio_urls == []
    assert refreshed_student.degree_title == "CS"  # not personally identifying alone, kept

    assert db_session.query(Device).filter(Device.user_id == student_user_id).count() == 0

    # The contract/milestone/message/rating rows survive — the other
    # party's legitimate record is untouched.
    assert db_session.query(Contract).filter(Contract.student_id == student.id).count() == 1
    assert db_session.query(Message).filter(Message.sender_user_id == student_user_id).count() == 1
    assert db_session.query(Rating).filter(Rating.rater_user_id == student_user_id).count() == 1
