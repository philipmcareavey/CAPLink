"""
Technical Implementation Plan 8.a.iii. Covers the parts of the SAML SSO
flow that don't need a signed assertion: SP metadata generation (works
even before a university's IdP is configured — see saml.py's own
docstring) and the "SSO not enabled" 404 on both the login and ACS routes.

**Known, deliberately flagged gap, not silently dropped**: the actual
assertion-consumer path (a real IdP POSTing a signed SAML Response) is NOT
covered here. That was verified once, manually, via a hand-built
XML-DSig-signed assertion against a self-signed test IdP certificate (see
caplink/CLAUDE.md's Epic 2.b entry) — real, thorough verification at the
time, but never captured as a permanent test, and rebuilding that harness
(generating a certificate, constructing a spec-correct SAML Response,
signing it with xmlsec, and getting SAML_BASE_URL/TestClient's base_url
onto a real dotted domain since python3-saml rejects single-label hosts
like "testserver") is real, separate, non-trivial work. Left for a
follow-up session rather than attempted here at the expense of the rest
of Workstream 8.
"""
from app.models.enums import UniversityLicenseStatus, UniversityLicenseTier
from app.models.university import University


def _seed_university(client, *, slug, saml_enabled=False) -> None:
    db = client.db_sessionmaker()
    try:
        db.add(
            University(
                name="SSO Test University",
                slug=slug,
                domain=f"{slug}.ac.uk",
                license_tier=UniversityLicenseTier.ENTERPRISE,
                license_status=UniversityLicenseStatus.ACTIVE,
                license_seats=100,
                primary_contact_name="Careers Team",
                primary_contact_email=f"careers@{slug}.ac.uk",
                saml_enabled=saml_enabled,
            )
        )
        db.commit()
    finally:
        db.close()


def test_metadata_endpoint_returns_valid_sp_metadata_even_when_sso_not_configured(client):
    _seed_university(client, slug="metauni", saml_enabled=False)
    resp = client.get("/api/v1/auth/saml/metauni/metadata")
    assert resp.status_code == 200, resp.text
    assert resp.headers["content-type"].startswith("application/xml")
    assert b"<md:EntityDescriptor" in resp.content
    assert b"<md:SPSSODescriptor" in resp.content


def test_metadata_endpoint_404s_for_an_unknown_university(client):
    resp = client.get("/api/v1/auth/saml/does-not-exist/metadata")
    assert resp.status_code == 404


def test_login_redirect_404s_when_sso_not_enabled_for_this_university(client):
    """2.b.iii's whole point: /auth/login stays untouched and this route
    simply doesn't exist for a university that hasn't opted in — not a
    broken partial SSO experience."""
    _seed_university(client, slug="nossouni", saml_enabled=False)
    resp = client.get("/api/v1/auth/saml/nossouni/login", follow_redirects=False)
    assert resp.status_code == 404


def test_acs_404s_when_sso_not_enabled_for_this_university(client):
    resp_uni_slug = "nossoacs"
    _seed_university(client, slug=resp_uni_slug, saml_enabled=False)
    resp = client.post(f"/api/v1/auth/saml/{resp_uni_slug}/acs", data={"SAMLResponse": "irrelevant"})
    assert resp.status_code == 404
