"""Technical Implementation Plan 8.a.iii — messaging and the
off-platform-contact flagging heuristic (messages.py's own module
docstring calls this "the safeguarding feature nobody else has"), plus a
genuine regression test for per-IP rate limiting (2.a.ii) actually
returning 429 — previously only verified manually, per caplink/CLAUDE.md's
Epic 2.a entry ("the full lockout-to-423 cycle... and hitting the rate
limit actually returns 429"), never captured as a permanent test.
"""
import base64
import json

from app.models.enums import StudentBand, UniversityLicenseStatus, UniversityLicenseTier
from app.models.university import University


def _decode_jwt_sub(token: str) -> str:
    payload_b64 = token.split(".")[1]
    payload_b64 += "=" * (-len(payload_b64) % 4)
    return json.loads(base64.urlsafe_b64decode(payload_b64))["sub"]


def _seed_university(client, *, slug="msguni") -> str:
    db = client.db_sessionmaker()
    try:
        university = University(
            name="Messaging Test University",
            slug=slug,
            domain=f"{slug}.ac.uk",
            license_tier=UniversityLicenseTier.ENTERPRISE,
            license_status=UniversityLicenseStatus.ACTIVE,
            license_seats=100,
            primary_contact_name="Careers Team",
            primary_contact_email=f"careers@{slug}.ac.uk",
        )
        db.add(university)
        db.commit()
        return university.id
    finally:
        db.close()


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _register(client, *, role, university_slug=None, email):
    if role == "student":
        resp = client.post(
            "/api/v1/auth/register/student",
            json={
                "email": email,
                "password": "Correct-Horse-Battery-42",
                "full_name": "Test Student",
                "university_slug": university_slug,
                "degree_title": "BSc Computer Science",
                "band": StudentBand.YEAR_3.value,
                "data_sharing_consent": True,
            },
        )
    else:
        resp = client.post(
            "/api/v1/auth/register/business",
            json={
                "email": email,
                "password": "Correct-Horse-Battery-99",
                "full_name": "Hiring Manager",
                "company_name": "Test Co",
            },
        )
    assert resp.status_code == 201, resp.text
    return resp.json()["access_token"]


def test_thread_and_flagging(client):
    university_slug = "msguni"
    _seed_university(client, slug=university_slug)
    student_token = _register(client, role="student", university_slug=university_slug, email="s@msguni.ac.uk")
    business_token = _register(client, role="business", email="b@example.com")

    # A student always needs a known counterpart to start a thread — there's
    # no generic "message anyone" form. The real frontend gets the other
    # user's id from wherever it already has it (an applicant list, a
    # contract card); here, decode it straight out of the business's own
    # access token, same as the frontend's decodeJwt() does.
    business_user_id = _decode_jwt_sub(business_token)

    thread_resp = client.post(
        "/api/v1/messages/threads",
        headers=_auth(student_token),
        json={"other_user_id": business_user_id, "project_id": None},
    )
    assert thread_resp.status_code == 201, thread_resp.text
    thread_id = thread_resp.json()["thread_id"]

    # An ordinary message is not flagged.
    clean_resp = client.post(
        "/api/v1/messages",
        headers=_auth(student_token),
        json={"thread_id": thread_id, "content": "Looking forward to getting started!"},
    )
    assert clean_resp.status_code == 201, clean_resp.text
    assert clean_resp.json()["is_flagged"] is False

    # A phone number gets flagged.
    phone_resp = client.post(
        "/api/v1/messages",
        headers=_auth(business_token),
        json={"thread_id": thread_id, "content": "Call me on 07911 123456 instead"},
    )
    assert phone_resp.status_code == 201, phone_resp.text
    # MessageOut deliberately doesn't expose *why* a message was flagged
    # back to whoever sent it (see app/schemas/message.py) — only
    # is_flagged is public; the reason is for moderators, not the sender.
    assert phone_resp.json()["is_flagged"] is True

    # A suspicious off-platform phrase gets flagged.
    phrase_resp = client.post(
        "/api/v1/messages",
        headers=_auth(student_token),
        json={"thread_id": thread_id, "content": "Could we take this outside the app?"},
    )
    assert phrase_resp.status_code == 201, phrase_resp.text
    assert phrase_resp.json()["is_flagged"] is True

    # A third party can't read or post into a conversation they're not part of.
    intruder_token = _register(client, role="business", email="intruder@example.com")
    forbidden_resp = client.post(
        "/api/v1/messages",
        headers=_auth(intruder_token),
        json={"thread_id": thread_id, "content": "I shouldn't be able to post here"},
    )
    assert forbidden_resp.status_code == 403, forbidden_resp.text


def test_send_message_rate_limit_actually_returns_429(client):
    """2.a.ii's per-IP rate limiting on messaging (60/minute on POST
    /messages) — verified manually per caplink/CLAUDE.md's Epic 2.a entry,
    never a permanent test until now."""
    university_slug = "ratelimituni"
    _seed_university(client, slug=university_slug)
    student_token = _register(
        client, role="student", university_slug=university_slug, email="s@ratelimituni.ac.uk"
    )
    business_token = _register(client, role="business", email="rl@example.com")

    thread_resp = client.post(
        "/api/v1/messages/threads",
        headers=_auth(student_token),
        json={"other_user_id": _decode_jwt_sub(business_token), "project_id": None},
    )
    thread_id = thread_resp.json()["thread_id"]

    statuses = [
        client.post(
            "/api/v1/messages",
            headers=_auth(student_token),
            json={"thread_id": thread_id, "content": f"message {i}"},
        ).status_code
        for i in range(61)
    ]
    assert 429 in statuses, "expected the 61st message within a minute to be rate-limited"
