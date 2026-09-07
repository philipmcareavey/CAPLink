from app.models.audit_log import AuditLog
from app.models.enums import UserRole
from app.models.university import University
from app.models.user import User
from app.services.audit_log import record_audit_event


def _make_admin(db_session):
    university = University(name="Test University", slug="test-uni-audit", domain="test-audit.ac.uk")
    db_session.add(university)
    db_session.flush()
    admin = User(
        email="admin@test-audit.ac.uk",
        hashed_password="not-a-real-hash",
        role=UserRole.UNIVERSITY_ADMIN,
        full_name="Admin",
        university_id=university.id,
        is_email_verified=True,
    )
    db_session.add(admin)
    db_session.flush()
    return admin


def test_record_audit_event_persists_all_fields(db_session):
    admin = _make_admin(db_session)

    entry = record_audit_event(
        db_session,
        actor_user_id=admin.id,
        action="agreement_decision",
        target_type="university_business_agreement",
        target_id="some-agreement-id",
        details={"status": "approved"},
    )
    db_session.commit()

    fetched = db_session.query(AuditLog).filter(AuditLog.id == entry.id).first()
    assert fetched is not None
    assert fetched.actor_user_id == admin.id
    assert fetched.action == "agreement_decision"
    assert fetched.target_type == "university_business_agreement"
    assert fetched.target_id == "some-agreement-id"
    assert fetched.details == {"status": "approved"}
    assert fetched.created_at is not None


def test_record_audit_event_allows_no_target_or_details(db_session):
    admin = _make_admin(db_session)

    entry = record_audit_event(
        db_session,
        actor_user_id=admin.id,
        action="university_onboarded",
        target_type="university",
    )
    db_session.commit()

    fetched = db_session.query(AuditLog).filter(AuditLog.id == entry.id).first()
    assert fetched is not None
    assert fetched.target_id is None
    assert fetched.details is None
