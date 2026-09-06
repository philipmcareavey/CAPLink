"""
University SAML SSO — Service Provider side (Technical Implementation Plan
step 2.b.i/2.b.ii). CAPLink is the SP; each university that enables SSO
configures their own IdP details on their University row (2.b.iii: this is
additive per-tenant config, not a global switch — a university with none of
this set just keeps using /auth/login exactly as before).

Real-world caveat worth being upfront about: most institutional SAML
federations (e.g. the UK Access Management Federation) expose identity
attributes (email, display name, an eduPersonAffiliation of "member"/
"student"/"staff"/...) but NOT CAPLink-specific concepts like "which
StudentBand" or "degree title" — those aren't standard eduPerson claims.
DEFAULT_ATTRIBUTE_MAPPING reflects that reality: it maps what's actually
commonly available, and JIT-provisioned students get a clearly-marked
placeholder degree_title/band to fill in via the existing profile-update
endpoint after their first login, rather than pretending SSO can conjure
data most IdPs were never going to send.
"""
from typing import Optional

from fastapi import Request
from onelogin.saml2.idp_metadata_parser import OneLogin_Saml2_IdPMetadataParser

from app.models.enums import StudentBand, UserRole
from app.models.university import University

# Common eduPerson / UK federation attribute URIs — used when a university
# hasn't configured saml_attribute_mapping of its own. Keyed by CAPLink
# concept, valued as the SAML attribute name to read.
DEFAULT_ATTRIBUTE_MAPPING = {
    "email": "urn:oid:0.9.2342.19200300.100.1.3",  # mail
    "full_name": "urn:oid:2.16.840.1.113730.3.1.241",  # displayName
    "affiliation": "urn:oid:1.3.6.1.4.1.5923.1.1.1.1",  # eduPersonAffiliation
    # Not standard eduPerson claims — only ever populated if a specific
    # university's IdP happens to expose a local/custom attribute for them
    # and configures saml_attribute_mapping to say so.
    "band": None,
    "degree_title": None,
}

PLACEHOLDER_DEGREE_TITLE = "Not yet set — update your profile"
DEFAULT_JIT_BAND = StudentBand.YEAR_1

ADMIN_AFFILIATION_VALUES = {"staff", "faculty", "employee"}


def normalize_x509_cert(cert: str) -> str:
    """python3-saml wants the raw base64 body, not a PEM-wrapped block —
    strip headers/whitespace if someone pastes a full PEM cert in."""
    lines = [
        line.strip()
        for line in cert.strip().splitlines()
        if line.strip() and "BEGIN CERTIFICATE" not in line and "END CERTIFICATE" not in line
    ]
    return "".join(lines)


def build_settings(university: University, base_url: str) -> dict:
    """base_url e.g. 'https://caplink-api.onrender.com/api/v1/auth/saml' —
    everything SAML-related for this university lives under
    {base_url}/{slug}/..., so the SP entity/ACS URLs are per-university
    paths even though it's the same backend handling all of them."""
    tenant_base = f"{base_url}/{university.slug}"
    return {
        "strict": True,
        "debug": False,
        "sp": {
            "entityId": f"{tenant_base}/metadata",
            "assertionConsumerService": {
                "url": f"{tenant_base}/acs",
                "binding": "urn:oasis:names:tc:SAML:2.0:bindings:HTTP-POST",
            },
            "NameIDFormat": "urn:oasis:names:tc:SAML:1.1:nameid-format:emailAddress",
            "x509cert": "",
            "privateKey": "",
        },
        "idp": {
            "entityId": university.saml_idp_entity_id,
            "singleSignOnService": {
                "url": university.saml_idp_sso_url,
                "binding": "urn:oasis:names:tc:SAML:2.0:bindings:HTTP-Redirect",
            },
            "x509cert": normalize_x509_cert(university.saml_idp_x509_cert or ""),
        },
        "security": {
            "wantAssertionsSigned": True,
            "wantMessagesSigned": False,
            "wantNameIdEncrypted": False,
            "requestedAuthnContext": False,
        },
    }


async def build_request_data(request: Request) -> dict:
    """Converts a FastAPI Request into the plain dict OneLogin_Saml2_Auth
    expects — it's written against Flask/Django's request objects, not
    ASGI/Starlette ones, so this is a small translation layer."""
    form: dict = {}
    if request.method == "POST":
        form_data = await request.form()
        form = dict(form_data)
    return {
        "https": "on" if request.url.scheme == "https" else "off",
        "http_host": request.url.hostname,
        "server_port": request.url.port,
        "script_name": request.url.path,
        "get_data": dict(request.query_params),
        "post_data": form,
    }


def map_attributes(raw_attributes: dict, mapping: Optional[dict]) -> dict:
    """raw_attributes is what OneLogin_Saml2_Auth.get_attributes() returns:
    {attribute_name: [values]}. Returns CAPLink-shaped fields, with a
    university's saml_attribute_mapping overriding DEFAULT_ATTRIBUTE_MAPPING
    per-key (not wholesale — a university only needs to configure the keys
    that differ from the default)."""
    effective_mapping = {**DEFAULT_ATTRIBUTE_MAPPING, **(mapping or {})}

    def _first(concept: str) -> Optional[str]:
        attr_name = effective_mapping.get(concept)
        if not attr_name:
            return None
        values = raw_attributes.get(attr_name)
        return values[0] if values else None

    return {
        "email": _first("email"),
        "full_name": _first("full_name"),
        "affiliation": [v.lower() for v in (raw_attributes.get(effective_mapping["affiliation"]) or [])],
        "band": _first("band"),
        "degree_title": _first("degree_title"),
    }


def parse_idp_metadata(metadata_xml: str) -> dict:
    """Backend half of 2.b.iv's 'metadata upload' — a university IT team
    exports one XML file from their IdP and this extracts everything
    CAPLink needs from it, instead of them hand-copying an entity ID, an
    SSO URL, and a certificate into three separate fields (error-prone,
    especially the certificate). The actual upload *screen* is a Workstream
    5 (frontend) concern; this is the endpoint it would call.

    Raises ValueError with a user-facing reason on anything that doesn't
    parse as valid, complete IdP metadata."""
    try:
        parsed = OneLogin_Saml2_IdPMetadataParser.parse(metadata_xml)
    except Exception as exc:
        raise ValueError(f"Could not parse IdP metadata: {exc}") from exc

    idp = parsed.get("idp", {})
    entity_id = idp.get("entityId")
    sso_url = idp.get("singleSignOnService", {}).get("url")
    x509_cert = idp.get("x509cert")
    if not entity_id or not sso_url or not x509_cert:
        raise ValueError(
            "IdP metadata is missing an entity ID, an HTTP-Redirect-binding SSO URL, or a signing certificate"
        )
    return {"entity_id": entity_id, "sso_url": sso_url, "x509_cert": x509_cert}


def infer_role(affiliation: list[str]) -> UserRole:
    """Only ever returns STUDENT or UNIVERSITY_ADMIN — never PLATFORM_ADMIN
    (that's CAPLink's own internal staff, never IdP-driven). Callers must
    NOT auto-create a new account when this returns UNIVERSITY_ADMIN — see
    the safety note in app/api/v1/endpoints/saml.py's ACS handler for why."""
    if any(value in ADMIN_AFFILIATION_VALUES for value in affiliation):
        return UserRole.UNIVERSITY_ADMIN
    return UserRole.STUDENT
