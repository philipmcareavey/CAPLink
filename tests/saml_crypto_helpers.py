"""Test-only helper for building a real, cryptographically signed SAML 2.0
Response — the piece test_saml_endpoints_e2e.py's own docstring flags as
"real, separate, non-trivial work. Left for a follow-up session." This is
that follow-up: a self-signed test IdP certificate (via `cryptography`) and
a hand-built, spec-shaped SAML Response with its Assertion signed via
`xmlsec` (enveloped XML-DSig, matching what a real IdP produces and what
python3-saml's OneLogin_Saml2_Auth.process_response() actually validates).

Not app code — nothing here is imported by app/.
"""
import base64
import uuid
from datetime import datetime, timedelta, timezone

import xmlsec
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID
from lxml import etree

SAML_NS = "urn:oasis:names:tc:SAML:2.0:assertion"
SAMLP_NS = "urn:oasis:names:tc:SAML:2.0:protocol"


def generate_self_signed_idp_cert() -> tuple[bytes, bytes, str]:
    """Returns (private_key_pem, cert_pem, cert_der_base64) — the last one
    is what gets stored on University.saml_idp_x509_cert, exactly the shape
    a real university's IT team would paste in from their IdP's own
    metadata."""
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "Test IdP")])
    now = datetime.now(timezone.utc)
    cert = (
        x509.CertificateBuilder()
        .subject_name(name)
        .issuer_name(name)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - timedelta(days=1))
        .not_valid_after(now + timedelta(days=365))
        .sign(key, hashes.SHA256())
    )
    key_pem = key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.TraditionalOpenSSL,
        encryption_algorithm=serialization.NoEncryption(),
    )
    cert_pem = cert.public_bytes(serialization.Encoding.PEM)
    cert_der_b64 = base64.b64encode(cert.public_bytes(serialization.Encoding.DER)).decode()
    return key_pem, cert_pem, cert_der_b64


def _fmt(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def build_signed_saml_response(
    *,
    idp_entity_id: str,
    sp_entity_id: str,
    acs_url: str,
    name_id: str,
    attributes: dict[str, list[str]],
    key_pem: bytes,
    cert_pem: bytes,
) -> str:
    """Builds a full <samlp:Response> with a signed <saml:Assertion> inside
    it, base64-encoded ready to POST as the SAMLResponse form field (POST
    binding — no deflate, unlike the redirect binding)."""
    now = datetime.now(timezone.utc)
    not_before = now - timedelta(minutes=5)
    not_after = now + timedelta(minutes=5)
    response_id = "_" + uuid.uuid4().hex
    assertion_id = "_" + uuid.uuid4().hex

    nsmap = {"samlp": SAMLP_NS, "saml": SAML_NS}
    response = etree.Element(
        f"{{{SAMLP_NS}}}Response",
        nsmap=nsmap,
        attrib={"ID": response_id, "Version": "2.0", "IssueInstant": _fmt(now), "Destination": acs_url},
    )
    resp_issuer = etree.SubElement(response, f"{{{SAML_NS}}}Issuer")
    resp_issuer.text = idp_entity_id
    status = etree.SubElement(response, f"{{{SAMLP_NS}}}Status")
    etree.SubElement(status, f"{{{SAMLP_NS}}}StatusCode", Value="urn:oasis:names:tc:SAML:2.0:status:Success")

    assertion = etree.SubElement(
        response,
        f"{{{SAML_NS}}}Assertion",
        attrib={"ID": assertion_id, "Version": "2.0", "IssueInstant": _fmt(now)},
    )
    assertion_issuer = etree.SubElement(assertion, f"{{{SAML_NS}}}Issuer")
    assertion_issuer.text = idp_entity_id

    subject = etree.SubElement(assertion, f"{{{SAML_NS}}}Subject")
    name_id_el = etree.SubElement(
        subject, f"{{{SAML_NS}}}NameID", Format="urn:oasis:names:tc:SAML:1.1:nameid-format:emailAddress"
    )
    name_id_el.text = name_id
    subject_confirmation = etree.SubElement(
        subject, f"{{{SAML_NS}}}SubjectConfirmation", Method="urn:oasis:names:tc:SAML:2.0:cm:bearer"
    )
    etree.SubElement(
        subject_confirmation,
        f"{{{SAML_NS}}}SubjectConfirmationData",
        Recipient=acs_url,
        NotOnOrAfter=_fmt(not_after),
    )

    conditions = etree.SubElement(
        assertion, f"{{{SAML_NS}}}Conditions", NotBefore=_fmt(not_before), NotOnOrAfter=_fmt(not_after)
    )
    audience_restriction = etree.SubElement(conditions, f"{{{SAML_NS}}}AudienceRestriction")
    audience = etree.SubElement(audience_restriction, f"{{{SAML_NS}}}Audience")
    audience.text = sp_entity_id

    authn_statement = etree.SubElement(
        assertion,
        f"{{{SAML_NS}}}AuthnStatement",
        AuthnInstant=_fmt(now),
        SessionIndex="_" + uuid.uuid4().hex,
    )
    authn_context = etree.SubElement(authn_statement, f"{{{SAML_NS}}}AuthnContext")
    authn_context_class_ref = etree.SubElement(authn_context, f"{{{SAML_NS}}}AuthnContextClassRef")
    authn_context_class_ref.text = "urn:oasis:names:tc:SAML:2.0:ac:classes:PasswordProtectedTransport"

    if attributes:
        attribute_statement = etree.SubElement(assertion, f"{{{SAML_NS}}}AttributeStatement")
        for attr_name, values in attributes.items():
            attr = etree.SubElement(
                attribute_statement,
                f"{{{SAML_NS}}}Attribute",
                Name=attr_name,
            )
            attr.set("NameFormat", "urn:oasis:names:tc:SAML:2.0:attrname-format:uri")
            for value in values:
                attr_value = etree.SubElement(attr, f"{{{SAML_NS}}}AttributeValue")
                attr_value.text = value

    # Real XML-DSig enveloped signature over the Assertion, matching what a
    # real IdP produces — python3-saml's own validator rejects an assertion
    # that merely claims wantAssertionsSigned without an actual, verifiable
    # <ds:Signature>.
    signature_node = xmlsec.template.create(
        assertion,
        xmlsec.constants.TransformExclC14N,
        xmlsec.constants.TransformRsaSha256,
    )
    # Spec placement: Signature comes directly after Issuer, before Subject.
    assertion.insert(1, signature_node)
    reference = xmlsec.template.add_reference(
        signature_node, xmlsec.constants.TransformSha256, uri="#" + assertion_id
    )
    xmlsec.template.add_transform(reference, xmlsec.constants.TransformEnveloped)
    xmlsec.template.add_transform(reference, xmlsec.constants.TransformExclC14N)
    key_info = xmlsec.template.ensure_key_info(signature_node)
    xmlsec.template.add_x509_data(key_info)

    xmlsec.tree.add_ids(assertion, ["ID"])
    ctx = xmlsec.SignatureContext()
    key = xmlsec.Key.from_memory(key_pem, xmlsec.constants.KeyDataFormatPem)
    key.load_cert_from_memory(cert_pem, xmlsec.constants.KeyDataFormatCertPem)
    ctx.key = key
    ctx.sign(signature_node)

    return base64.b64encode(etree.tostring(response)).decode()
