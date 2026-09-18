"""Real HTTP tests for GET/PATCH /api/v1/mobile/notification-preferences
(app/api/v1/endpoints/mobile.py) and the delivery-blocking behaviour it
controls in app/services/notifications.py::notify_from_template.

Field names (`preferences`, `template_key`, `label`, `enabled`, request
field `opted_out`) are relied on exactly by a parallel worker building the
mobile UI against this same contract — don't rename them.
"""
from app.services import notifications

from tests.test_golden_path_e2e import _seed_university
from tests.test_messaging_e2e import _auth, _decode_jwt_sub, _register


def test_get_preferences_defaults_to_every_template_enabled(client):
    _seed_university(client, slug="notifprefuni", domain="notifprefuni.ac.uk")
    token = _register(client, role="student", university_slug="notifprefuni", email="prefs1@notifprefuni.ac.uk")

    resp = client.get("/api/v1/mobile/notification-preferences", headers=_auth(token))
    assert resp.status_code == 200, resp.text
    prefs = resp.json()["preferences"]

    expected_keys = set(notifications.NOTIFICATION_TEMPLATES.keys())
    assert {p["template_key"] for p in prefs} == expected_keys
    assert len(prefs) == len(expected_keys)
    assert all(p["enabled"] is True for p in prefs)


def test_patch_opts_out_one_template_and_persists(client):
    _seed_university(client, slug="notifprefuni2", domain="notifprefuni2.ac.uk")
    token = _register(client, role="student", university_slug="notifprefuni2", email="prefs2@notifprefuni2.ac.uk")

    patch = client.patch(
        "/api/v1/mobile/notification-preferences", headers=_auth(token), json={"opted_out": ["new_message"]}
    )
    assert patch.status_code == 200, patch.text
    prefs_by_key = {p["template_key"]: p["enabled"] for p in patch.json()["preferences"]}
    assert prefs_by_key["new_message"] is False
    assert all(enabled for key, enabled in prefs_by_key.items() if key != "new_message")

    follow_up = client.get("/api/v1/mobile/notification-preferences", headers=_auth(token))
    assert follow_up.status_code == 200
    follow_up_by_key = {p["template_key"]: p["enabled"] for p in follow_up.json()["preferences"]}
    assert follow_up_by_key["new_message"] is False


def test_patch_with_unknown_template_key_returns_400(client):
    _seed_university(client, slug="notifprefuni3", domain="notifprefuni3.ac.uk")
    token = _register(client, role="student", university_slug="notifprefuni3", email="prefs3@notifprefuni3.ac.uk")

    resp = client.patch(
        "/api/v1/mobile/notification-preferences", headers=_auth(token), json={"opted_out": ["not_a_real_key"]}
    )
    assert resp.status_code == 400, resp.text


def test_opting_out_genuinely_blocks_delivery_while_others_still_receive(client, monkeypatch):
    """Real end-to-end proof: opt a student out of `new_message`, then
    trigger a real new-message notification the way the messaging flow
    already does (send_message -> notify_from_template), and confirm via a
    monkeypatched _send_push that nothing was sent to the opted-out
    student's device — while a business (never opted out) in the same
    thread still receives its own new-message notification for the reply."""
    _seed_university(client, slug="notifprefuni4", domain="notifprefuni4.ac.uk")
    student_token = _register(
        client, role="student", university_slug="notifprefuni4", email="opted-out@notifprefuni4.ac.uk"
    )
    business_token = _register(client, role="business", email="notif-business@example.com")
    business_user_id = _decode_jwt_sub(business_token)

    # Opt the student out of new_message notifications.
    opt_out = client.patch(
        "/api/v1/mobile/notification-preferences", headers=_auth(student_token), json={"opted_out": ["new_message"]}
    )
    assert opt_out.status_code == 200, opt_out.text

    # Register a real device for each side so notify_user() has something to push to.
    client.post(
        "/api/v1/mobile/devices",
        headers=_auth(student_token),
        json={"platform": "ios", "push_token": "student-device-token"},
    )
    client.post(
        "/api/v1/mobile/devices",
        headers=_auth(business_token),
        json={"platform": "android", "push_token": "business-device-token"},
    )

    calls = []
    monkeypatch.setattr(
        notifications, "_send_push", lambda db, device, title, body, data=None: calls.append(device.push_token)
    )

    thread_resp = client.post(
        "/api/v1/messages/threads",
        headers=_auth(student_token),
        json={"other_user_id": business_user_id, "project_id": None},
    )
    assert thread_resp.status_code == 201, thread_resp.text
    thread_id = thread_resp.json()["thread_id"]

    # Business messages the (opted-out) student — no push should reach the student's device.
    business_message = client.post(
        "/api/v1/messages",
        headers=_auth(business_token),
        json={"thread_id": thread_id, "content": "Hi there!"},
    )
    assert business_message.status_code == 201, business_message.text
    assert "student-device-token" not in calls, "opted-out student must not receive a push"

    # Student replies to the (never opted-out) business — that push must still go through.
    student_reply = client.post(
        "/api/v1/messages",
        headers=_auth(student_token),
        json={"thread_id": thread_id, "content": "Thanks, will take a look!"},
    )
    assert student_reply.status_code == 201, student_reply.text
    assert "business-device-token" in calls, "non-opted-out business must still receive a push"
