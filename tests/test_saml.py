from app.models.enums import UserRole
from app.services.saml import (
    DEFAULT_ATTRIBUTE_MAPPING,
    infer_role,
    map_attributes,
    normalize_x509_cert,
    parse_idp_metadata,
)

SAMPLE_IDP_METADATA = """<?xml version="1.0"?>
<md:EntityDescriptor xmlns:md="urn:oasis:names:tc:SAML:2.0:metadata" entityID="https://idp.testuni.ac.uk/idp/shibboleth">
  <md:IDPSSODescriptor protocolSupportEnumeration="urn:oasis:names:tc:SAML:2.0:protocol">
    <md:KeyDescriptor use="signing">
      <ds:KeyInfo xmlns:ds="http://www.w3.org/2000/09/xmldsig#">
        <ds:X509Data>
          <ds:X509Certificate>MIIDXTCCAkWgAwIBAgIJAJC1HiIAZAiIMA0GCSqGSIb3DQEBBQUAMEUxCzAJBgNV</ds:X509Certificate>
        </ds:X509Data>
      </ds:KeyInfo>
    </md:KeyDescriptor>
    <md:SingleSignOnService Binding="urn:oasis:names:tc:SAML:2.0:bindings:HTTP-Redirect" Location="https://idp.testuni.ac.uk/idp/profile/SAML2/Redirect/SSO"/>
  </md:IDPSSODescriptor>
</md:EntityDescriptor>"""


def test_normalize_x509_cert_strips_pem_headers_and_whitespace():
    pem = "-----BEGIN CERTIFICATE-----\nABCD\nEFGH\n-----END CERTIFICATE-----\n"
    assert normalize_x509_cert(pem) == "ABCDEFGH"


def test_normalize_x509_cert_passes_through_raw_base64_unchanged():
    assert normalize_x509_cert("ABCDEFGH") == "ABCDEFGH"


def test_parse_idp_metadata_extracts_the_three_required_fields():
    result = parse_idp_metadata(SAMPLE_IDP_METADATA)
    assert result["entity_id"] == "https://idp.testuni.ac.uk/idp/shibboleth"
    assert result["sso_url"] == "https://idp.testuni.ac.uk/idp/profile/SAML2/Redirect/SSO"
    assert result["x509_cert"].startswith("MIIDXTCC")


def test_parse_idp_metadata_rejects_garbage():
    import pytest
    from app.services.saml import parse_idp_metadata as _parse

    with pytest.raises(ValueError):
        _parse("this is not xml at all")


def test_map_attributes_uses_default_mapping():
    raw = {
        DEFAULT_ATTRIBUTE_MAPPING["email"]: ["aisha@manchester.ac.uk"],
        DEFAULT_ATTRIBUTE_MAPPING["full_name"]: ["Aisha Rahman"],
        DEFAULT_ATTRIBUTE_MAPPING["affiliation"]: ["member", "student"],
    }
    mapped = map_attributes(raw, mapping=None)
    assert mapped["email"] == "aisha@manchester.ac.uk"
    assert mapped["full_name"] == "Aisha Rahman"
    assert mapped["affiliation"] == ["member", "student"]
    assert mapped["band"] is None
    assert mapped["degree_title"] is None


def test_map_attributes_respects_a_university_specific_override():
    raw = {"mail-custom": ["hi@custom.ac.uk"], "yearOfStudy": ["year_2"]}
    custom_mapping = {"email": "mail-custom", "band": "yearOfStudy"}
    mapped = map_attributes(raw, mapping=custom_mapping)
    assert mapped["email"] == "hi@custom.ac.uk"
    assert mapped["band"] == "year_2"


def test_map_attributes_handles_missing_attributes_gracefully():
    mapped = map_attributes({}, mapping=None)
    assert mapped["email"] is None
    assert mapped["affiliation"] == []


def test_infer_role_defaults_to_student():
    assert infer_role([]) == UserRole.STUDENT
    assert infer_role(["member", "student"]) == UserRole.STUDENT


def test_infer_role_detects_staff_affiliation():
    assert infer_role(["member", "staff"]) == UserRole.UNIVERSITY_ADMIN
    assert infer_role(["faculty"]) == UserRole.UNIVERSITY_ADMIN
