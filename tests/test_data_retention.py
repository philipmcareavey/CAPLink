"""
scripts/data_retention.py operates on app.db.session.SessionLocal (a real
module-level sessionmaker bound to whatever DATABASE_URL is configured),
not the db_session fixture's isolated in-memory engine used elsewhere in
this test suite — so these tests point SessionLocal at a temporary SQLite
file for the duration of each test rather than reusing that fixture.
"""
import os
import tempfile
from datetime import datetime, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.base_class import Base
from app.models.enums import UserRole
from app.models.recommendation import RecommendationLog
from app.models.user import User


@pytest.fixture()
def retention_db(monkeypatch):
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    engine = create_engine(f"sqlite:///{path}", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    TestSessionLocal = sessionmaker(bind=engine)

    import app.db.session as db_session_module
    import scripts.data_retention as data_retention_module

    monkeypatch.setattr(db_session_module, "SessionLocal", TestSessionLocal)
    monkeypatch.setattr(data_retention_module, "SessionLocal", TestSessionLocal)

    session = TestSessionLocal()
    yield session
    session.close()
    engine.dispose()
    os.remove(path)


def _make_user(db, **overrides):
    defaults = dict(
        email=f"user-{overrides.get('email_suffix', 'x')}@example.com",
        hashed_password="x", role=UserRole.STUDENT, full_name="U", is_email_verified=True,
    )
    defaults.update({k: v for k, v in overrides.items() if k != "email_suffix"})
    user = User(**defaults)
    db.add(user)
    db.flush()
    return user


def test_dry_run_reports_without_changing_anything(retention_db):
    from scripts.data_retention import run

    old_unverified = _make_user(
        retention_db, email_suffix="old-unverified", is_email_verified=False,
        created_at=datetime.utcnow() - timedelta(days=40),
    )
    retention_db.commit()

    report = run(execute=False)
    assert report["unverified_deleted"] == 1

    # Nothing actually changed — dry run.
    still_there = retention_db.query(User).filter(User.id == old_unverified.id).first()
    assert still_there is not None


def test_execute_deletes_old_unverified_accounts(retention_db):
    from scripts.data_retention import run

    old_unverified = _make_user(
        retention_db, email_suffix="old-unverified2", is_email_verified=False,
        created_at=datetime.utcnow() - timedelta(days=40),
    )
    recent_unverified = _make_user(
        retention_db, email_suffix="recent-unverified", is_email_verified=False,
        created_at=datetime.utcnow() - timedelta(days=2),
    )
    retention_db.commit()

    old_unverified_id, recent_unverified_id = old_unverified.id, recent_unverified.id
    report = run(execute=True)
    assert report["unverified_deleted"] == 1

    # run() deletes via its own separate session (SessionLocal() call) —
    # expire this session's identity map so the check below issues a fresh
    # query rather than erroring on a locally-cached now-deleted instance.
    retention_db.expire_all()
    assert retention_db.query(User).filter(User.id == old_unverified_id).first() is None
    assert retention_db.query(User).filter(User.id == recent_unverified_id).first() is not None


def test_execute_anonymizes_long_inactive_verified_accounts(retention_db):
    from scripts.data_retention import run

    inactive = _make_user(
        retention_db, email_suffix="long-inactive", is_email_verified=True,
        last_login_at=datetime.utcnow() - timedelta(days=800),
    )
    active = _make_user(
        retention_db, email_suffix="still-active", is_email_verified=True,
        last_login_at=datetime.utcnow() - timedelta(days=5),
    )
    retention_db.commit()

    report = run(execute=True)
    assert report["inactive_anonymized"] == 1

    refreshed_inactive = retention_db.query(User).filter(User.id == inactive.id).first()
    assert refreshed_inactive.deleted_at is not None
    assert refreshed_inactive.email.startswith("deleted-user-")

    refreshed_active = retention_db.query(User).filter(User.id == active.id).first()
    assert refreshed_active.deleted_at is None


def test_execute_purges_old_recommendation_logs(retention_db):
    from scripts.data_retention import run

    user = _make_user(retention_db, email_suffix="rec-log-user", is_email_verified=True)
    retention_db.flush()
    old_log = RecommendationLog(
        user_id=user.id, entity_type="project", entity_id="e1", score=0.5,
        created_at=datetime.utcnow() - timedelta(days=400),
    )
    recent_log = RecommendationLog(
        user_id=user.id, entity_type="project", entity_id="e2", score=0.5,
        created_at=datetime.utcnow() - timedelta(days=10),
    )
    retention_db.add_all([old_log, recent_log])
    retention_db.commit()

    report = run(execute=True)
    assert report["recommendation_logs_deleted"] == 1

    remaining = retention_db.query(RecommendationLog).filter(RecommendationLog.user_id == user.id).all()
    assert len(remaining) == 1
    assert remaining[0].entity_id == "e2"
