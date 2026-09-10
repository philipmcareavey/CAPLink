import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.models  # noqa: F401 — registers all models with Base.metadata
from app.db.base_class import Base


@pytest.fixture()
def db_session():
    """A fresh in-memory SQLite database per test — fast, isolated, no
    fixtures leaking between tests."""
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


@pytest.fixture()
def client(monkeypatch):
    """A real TestClient against the actual app (app.main.app), for genuine
    integration/E2E tests that exercise routing, dependency injection, and
    auth exactly as a real request would — the thing this project's test
    suite never actually did before Workstream 8 (every prior test called
    service functions directly with a bare db_session, bypassing the app
    entirely).

    Deliberately does NOT use `with TestClient(app) as c:` — entering the
    context manager fires the ASGI lifespan protocol, which runs
    app.main.py's on_startup() hook: real Alembic migrations plus, in
    development (the default), auto-seeding demo data — both against
    app.db.session's real global `engine`, i.e. this Mac's actual
    ./caplink.db, not this fixture's isolated one. Skipping the context
    manager skips lifespan entirely; nothing this app needs at request time
    (rate limiting, middleware, routes) is set up inside on_startup, so
    ordinary requests work identically either way — see app/main.py.

    Per-test isolation via a fresh in-memory SQLite engine (StaticPool
    keeps one connection alive for the engine's lifetime, since plain
    in-memory SQLite doesn't share state across the separate connections
    TestClient's threaded requests would otherwise open) and a `get_db`
    dependency override — the same function object every endpoint's
    `Depends(get_db)` resolves to, so the override reaches every request
    regardless of how deep in the dependency chain it's used.
    """
    # Never let a real HaveIBeenPwned outage or slowness affect this
    # fixture's own reliability — the live breach check already has its own
    # dedicated test (test_password_policy.py::test_live_hibp...); every
    # other test using this fixture cares about the registration flow
    # itself, not re-proving that check against a real network call.
    from app.core.config import settings

    monkeypatch.setattr(settings, "PASSWORD_BREACH_CHECK_ENABLED", False)

    from app.db.session import get_db
    from app.main import app

    # app.state.limiter (app/core/rate_limit.py) is a module-level Limiter
    # singleton — real, and shared across every test in the whole pytest
    # session, since `app` itself is only ever imported once. Without this,
    # a test late in the run could get a spurious 429 from register/login
    # calls earlier tests already made against the same in-memory counters,
    # for a limit this test has nothing to do with. Resetting per test
    # keeps each one's rate-limit state genuinely isolated; slowapi/rate
    # limiting has its own coverage to actually test the 429 behaviour.
    app.state.limiter.reset()
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    test_client = TestClient(app)
    # A few things (creating a University, an already-APPROVED business
    # agreement) have no public endpoint at all — onboarding a university
    # is platform-admin-only, and there's no self-registration path to
    # *become* a platform admin. Tests that need that baseline state seed
    # it directly via ORM, against this exact engine, through this
    # attribute — same shape as the existing db_session fixture, just
    # sharing the client's own database instead of a separate one.
    test_client.db_sessionmaker = TestingSessionLocal
    try:
        yield test_client
    finally:
        app.dependency_overrides.pop(get_db, None)
        engine.dispose()
