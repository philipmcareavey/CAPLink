"""Technical Implementation Plan 8.a.i — the one genuinely-untested SAML
surface flagged (twice) as deliberately deferred: a real IdP POSTing a
cryptographically signed SAML Response to the ACS endpoint. See
tests/test_saml_endpoints_e2e.py's own docstring and
tests/saml_crypto_helpers.py for why this needed its own dedicated harness
(a real self-signed cert, a spec-shaped Response, real XML-DSig signing via
xmlsec) rather than being folded into the non-crypto-path file.

Same gotcha noted in caplink/CLAUDE.md's Epic 2.b entry: TestClient's
default `Host` header is the single-label `testserver`, which python3-saml
rejects outright (not a dotted domain) — and even if it weren't rejected,
a mismatched Host vs. the SP's configured entity/ACS URLs would make the
Audience/Destination/Recipient checks fail in confusing ways. Both this
file's SAML_BASE_URL (via monkeypatching the endpoint module's own
module-level constant — it's fixed at import time from
settings.PUBLIC_APP_URL, so patching the setting after import wouldn't
reach it) and its TestClient's base_url use a real dotted test domain,
http://caplink.test, for exactly this reason.
"""
from fastapi.testclient import TestClient

import app.api.v1.endpoints.saml as saml_endpoint
from app.main import app as fastapi_app
from app.models.enums import UniversityLicenseStatus, UniversityLicenseTier
from app.models.university import University
from app.models.user import User

from tests.saml_crypto_helpers import build_signed_saml_response, generate_self_signed_idp_cert

TEST_BASE_URL = "http://caplink.test"
IDP_ENTITY_ID = "https://idp.test/metadata"
IDP_SSO_URL = "https://idp.test/sso"


def _crypto_client(monkeypatch) -> TestClient:
    """A second TestClient over the same app instance/dependency overrides
    the `client` fixture already set up, just with a real dotted base_url
    instead of TestClient's default single-label `testserver` — and the
    saml.py module's own SAML_BASE_URL patched to match, since it's a
    plain module-level string fixed at import time, not re-read from
    settings per-request."""
    monkeypatch.setattr(saml_endpoint, "SAML_BASE_URL", f"{TEST_BASE_URL}/api/v1/auth/saml")
    return TestClient(fastapi_app, base_url=TEST_BASE_URL)


def _seed_sso_university(client, *, slug, cert_der_b64) -> str:
    db = client.db_sessionmaker()
    try:
        university = University(
            name="Crypto SSO Test University",
            slug=slug,
            domain=f"{slug}.ac.uk",
            license_tier=UniversityLicenseTier.ENTERPRISE,
            license_status=UniversityLicenseStatus.ACTIVE,
            license_seats=100,
            primary_contact_name="Careers Team",
            primary_contact_email=f"careers@{slug}.ac.uk",
            saml_enabled=True,
            saml_idp_entity_id=IDP_ENTITY_ID,
            saml_idp_sso_url=IDP_SSO_URL,
            saml_idp_x509_cert=cert_der_b64,
        )
        db.add(university)
        db.commit()
        return university.id
    finally:
        db.close()


def _entity_and_acs_urls(slug: str) -> tuple[str, str]:
    tenant_base = f"{TEST_BASE_URL}/api/v1/auth/saml/{slug}"
    return f"{tenant_base}/metadata", f"{tenant_base}/acs"


def _decode_tokens_from_redirect(location: str) -> dict[str, str]:
    fragment = location.split("#", 1)[1]
    return dict(pair.split("=", 1) for pair in fragment.split("&"))


def test_valid_signed_assertion_jit_provisions_a_student_and_issues_real_tokens(client, monkeypatch):
    crypto_client = _crypto_client(monkeypatch)
    key_pem, cert_pem, cert_der_b64 = generate_self_signed_idp_cert()
    slug = "cryptouni"
    _seed_sso_university(client, slug=slug, cert_der_b64=cert_der_b64)
    sp_entity_id, acs_url = _entity_and_acs_urls(slug)

    saml_response = build_signed_saml_response(
        idp_entity_id=IDP_ENTITY_ID,
        sp_entity_id=sp_entity_id,
        acs_url=acs_url,
        name_id="new.student@example.com",
        attributes={
            "urn:oid:0.9.2342.19200300.100.1.3": ["new.student@example.com"],
            "urn:oid:2.16.840.1.113730.3.1.241": ["New Student"],
            "urn:oid:1.3.6.1.4.1.5923.1.1.1.1": ["student"],
        },
        key_pem=key_pem,
        cert_pem=cert_pem,
    )

    resp = crypto_client.post(f"/api/v1/auth/saml/{slug}/acs", data={"SAMLResponse": saml_response}, follow_redirects=False)
    assert resp.status_code == 302, resp.text
    assert "sso_error" not in resp.headers["location"]
    tokens = _decode_tokens_from_redirect(resp.headers["location"])
    assert "access_token" in tokens and "refresh_token" in tokens

    db = client.db_sessionmaker()
    try:
        user = db.query(User).filter(User.email == "new.student@example.com").first()
        assert user is not None
        assert user.role.value == "student"
        assert user.is_email_verified is True
        assert user.full_name == "New Student"
    finally:
        db.close()

    # Logging in again via SSO must reuse the same account, not create a second one.
    saml_response_again = build_signed_saml_response(
        idp_entity_id=IDP_ENTITY_ID,
        sp_entity_id=sp_entity_id,
        acs_url=acs_url,
        name_id="new.student@example.com",
        attributes={
            "urn:oid:0.9.2342.19200300.100.1.3": ["new.student@example.com"],
            "urn:oid:2.16.840.1.113730.3.1.241": ["New Student"],
            "urn:oid:1.3.6.1.4.1.5923.1.1.1.1": ["student"],
        },
        key_pem=key_pem,
        cert_pem=cert_pem,
    )
    resp_again = crypto_client.post(
        f"/api/v1/auth/saml/{slug}/acs", data={"SAMLResponse": saml_response_again}, follow_redirects=False
    )
    assert resp_again.status_code == 302, resp_again.text
    assert "sso_error" not in resp_again.headers["location"]

    db = client.db_sessionmaker()
    try:
        matching_users = db.query(User).filter(User.email == "new.student@example.com").all()
        assert len(matching_users) == 1, "SSO must not create a second account on repeat login"
    finally:
        db.close()


def test_a_staff_affiliation_assertion_with_no_existing_account_is_rejected_not_auto_provisioned(client, monkeypatch):
    """The safeguarding-gate safety rule saml.py's ACS handler centres
    on: an IdP claiming "staff" must never auto-create a UNIVERSITY_ADMIN
    account. Zero rows should exist afterward."""
    crypto_client = _crypto_client(monkeypatch)
    key_pem, cert_pem, cert_der_b64 = generate_self_signed_idp_cert()
    slug = "staffcryptouni"
    _seed_sso_university(client, slug=slug, cert_der_b64=cert_der_b64)
    sp_entity_id, acs_url = _entity_and_acs_urls(slug)

    saml_response = build_signed_saml_response(
        idp_entity_id=IDP_ENTITY_ID,
        sp_entity_id=sp_entity_id,
        acs_url=acs_url,
        name_id="staffer@example.com",
        attributes={
            "urn:oid:0.9.2342.19200300.100.1.3": ["staffer@example.com"],
            "urn:oid:2.16.840.1.113730.3.1.241": ["A Staff Member"],
            "urn:oid:1.3.6.1.4.1.5923.1.1.1.1": ["staff"],
        },
        key_pem=key_pem,
        cert_pem=cert_pem,
    )

    resp = crypto_client.post(f"/api/v1/auth/saml/{slug}/acs", data={"SAMLResponse": saml_response}, follow_redirects=False)
    assert resp.status_code == 302, resp.text
    assert "sso_error=admin_account_not_provisioned" in resp.headers["location"]

    db = client.db_sessionmaker()
    try:
        assert db.query(User).filter(User.email == "staffer@example.com").first() is None
    finally:
        db.close()


def test_a_tampered_assertion_is_rejected_and_creates_no_account(client, monkeypatch):
    crypto_client = _crypto_client(monkeypatch)
    key_pem, cert_pem, cert_der_b64 = generate_self_signed_idp_cert()
    slug = "tampereduni"
    _seed_sso_university(client, slug=slug, cert_der_b64=cert_der_b64)
    sp_entity_id, acs_url = _entity_and_acs_urls(slug)

    saml_response = build_signed_saml_response(
        idp_entity_id=IDP_ENTITY_ID,
        sp_entity_id=sp_entity_id,
        acs_url=acs_url,
        name_id="tampered@example.com",
        attributes={
            "urn:oid:0.9.2342.19200300.100.1.3": ["tampered@example.com"],
            "urn:oid:1.3.6.1.4.1.5923.1.1.1.1": ["student"],
        },
        key_pem=key_pem,
        cert_pem=cert_pem,
    )
    # Flip the assertion's NameID content post-signing (on the decoded XML,
    # not the base64 string — base64 doesn't preserve ASCII substrings at
    # arbitrary byte offsets) — invalidates the signature over the assertion.
    import base64

    raw_xml = base64.b64decode(saml_response)
    tampered_xml = raw_xml.replace(b"tampered@example.com", b"attacker@example.com")
    assert tampered_xml != raw_xml, "tamper substitution should have matched something in the decoded XML"
    tampered = base64.b64encode(tampered_xml).decode()

    resp = crypto_client.post(f"/api/v1/auth/saml/{slug}/acs", data={"SAMLResponse": tampered}, follow_redirects=False)
    assert resp.status_code == 302, resp.text
    assert "sso_error=assertion_invalid" in resp.headers["location"]

    db = client.db_sessionmaker()
    try:
        assert db.query(User).filter(User.email == "attacker@example.com").first() is None
    finally:
        db.close()
