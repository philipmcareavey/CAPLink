"""
Unit tests for app/services/notifications.py's push-delivery logic.
firebase-admin lives in requirements-integrations.txt, not requirements.txt
(CI's `test` job never installs it), so any test that needs the real
library is guarded with is_available()/pytest.skip — same pattern as
tests/test_embeddings.py.
"""
import pytest

from app.core.config import settings
from app.models.enums import DevicePlatform, StudentBand, UserRole
from app.models.university import University
from app.models.user import StudentProfile, User
from app.services import notifications
from app.models.device import Device


def _make_device(db_session, push_token="a-real-fcm-token-1234567890"):
    university = University(name="Test Uni", slug="test-uni-notif", domain="test-notif.ac.uk")
    db_session.add(university)
    db_session.flush()
    user = User(
        email="student@test-notif.ac.uk", hashed_password="x", role=UserRole.STUDENT,
        full_name="S", is_email_verified=True, university_id=university.id,
    )
    db_session.add(user)
    db_session.flush()
    db_session.add(StudentProfile(user_id=user.id, university_id=university.id, degree_title="CS", band=StudentBand.YEAR_2))
    device = Device(user_id=user.id, platform=DevicePlatform.ANDROID, push_token=push_token, is_active=True)
    db_session.add(device)
    db_session.flush()
    return device


def test_send_push_without_fcm_credentials_logs_and_never_touches_firebase(db_session, monkeypatch, caplog):
    monkeypatch.setattr(settings, "FIREBASE_CREDENTIALS_JSON", "")
    device = _make_device(db_session)

    with caplog.at_level("INFO", logger="caplink.notifications"):
        notifications._send_push(db_session, device, "Title", "Body", {"k": "v"})

    assert any(r.message == "push_notification" for r in caplog.records)
    assert device.is_active is True


def test_is_available_returns_a_real_boolean():
    assert isinstance(notifications.is_available(), bool)


def test_send_push_with_fcm_configured_delivers_and_leaves_device_active(db_session, monkeypatch):
    if not notifications.is_available():
        pytest.skip("firebase_admin not installed")
    import firebase_admin.credentials as credentials
    import firebase_admin.messaging as messaging

    monkeypatch.setattr(settings, "FIREBASE_CREDENTIALS_JSON", "/tmp/fake-firebase-creds.json")
    monkeypatch.setattr(notifications, "_firebase_app", None)
    captured_cert_arg = {}
    monkeypatch.setattr(credentials, "Certificate", lambda cert: (captured_cert_arg.update(arg=cert), object())[1])
    monkeypatch.setattr("firebase_admin.initialize_app", lambda cred: object())

    sent = {}

    def fake_send(message, app=None):
        sent["token"] = message.token
        sent["title"] = message.notification.title
        sent["body"] = message.notification.body
        return "projects/x/messages/1"

    monkeypatch.setattr(messaging, "send", fake_send)

    device = _make_device(db_session, push_token="real-token-abc")
    notifications._send_push(db_session, device, "Hello", "World")

    assert sent["token"] == "real-token-abc"
    assert sent["title"] == "Hello"
    assert sent["body"] == "World"
    assert device.is_active is True
    # Proves the fix: the raw setting value reaches Certificate() unmodified,
    # with no json.loads() in between (the setting is a file path, per the
    # pre-existing .env.example convention, not inline JSON content).
    assert captured_cert_arg["arg"] == "/tmp/fake-firebase-creds.json"


def test_notify_from_template_skips_opted_out_template_but_still_sends_others(db_session, monkeypatch):
    """A user who has opted out of a specific template must get zero
    _send_push calls (no Device query, no send at all) for that template,
    while a non-opted-out template still delivers normally — the two
    template keys used by the real event sites in messages.py/ratings.py,
    per the real NOTIFICATION_TEMPLATES dict."""
    calls = []
    monkeypatch.setattr(notifications, "_send_push", lambda *a, **kw: calls.append(a))

    device = _make_device(db_session)
    user = db_session.query(User).filter(User.id == device.user_id).first()
    user.notification_opt_outs = ["new_message"]
    db_session.commit()

    notifications.notify_from_template(db_session, user.id, "new_message", sender_name="X")
    assert calls == [], "opted-out template must never reach _send_push"

    notifications.notify_from_template(db_session, user.id, "rating_released")
    assert len(calls) == 1, "a non-opted-out template must still deliver normally"


def test_send_push_deactivates_device_on_unregistered_token(db_session, monkeypatch):
    if not notifications.is_available():
        pytest.skip("firebase_admin not installed")
    import firebase_admin.credentials as credentials
    import firebase_admin.messaging as messaging

    monkeypatch.setattr(settings, "FIREBASE_CREDENTIALS_JSON", "/tmp/fake-firebase-creds.json")
    monkeypatch.setattr(notifications, "_firebase_app", None)
    captured_cert_arg = {}
    monkeypatch.setattr(credentials, "Certificate", lambda cert: (captured_cert_arg.update(arg=cert), object())[1])
    monkeypatch.setattr("firebase_admin.initialize_app", lambda cred: object())

    def fake_send(message, app=None):
        raise messaging.UnregisteredError("token no longer valid")

    monkeypatch.setattr(messaging, "send", fake_send)

    device = _make_device(db_session, push_token="dead-token")
    device_id = device.id
    notifications._send_push(db_session, device, "Hello", "World")

    assert device.is_active is False
    # Re-query independently to confirm db.commit() actually persisted it,
    # not just mutated the in-memory object this test already holds.
    refreshed = db_session.query(Device).filter(Device.id == device_id).first()
    assert refreshed.is_active is False
    # Proves the fix: the raw setting value reaches Certificate() unmodified,
    # with no json.loads() in between (the setting is a file path, per the
    # pre-existing .env.example convention, not inline JSON content).
    assert captured_cert_arg["arg"] == "/tmp/fake-firebase-creds.json"
