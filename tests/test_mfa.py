import pyotp

from app.services.mfa import (
    BACKUP_CODE_COUNT,
    consume_backup_code,
    generate_backup_codes,
    generate_totp_secret,
    hash_backup_codes,
    provisioning_uri,
    verify_totp_code,
)


def test_generated_secret_is_a_valid_base32_totp_secret():
    secret = generate_totp_secret()
    # Round-trips through pyotp without raising, and produces a 6-digit code.
    code = pyotp.TOTP(secret).now()
    assert len(code) == 6 and code.isdigit()


def test_provisioning_uri_contains_the_issuer_and_account_name():
    secret = generate_totp_secret()
    uri = provisioning_uri(secret, "admin@manchester.ac.uk")
    assert uri.startswith("otpauth://totp/")
    assert "CAPLink" in uri
    assert "admin%40manchester.ac.uk" in uri or "admin@manchester.ac.uk" in uri


def test_verify_totp_code_accepts_the_current_code():
    secret = generate_totp_secret()
    current_code = pyotp.TOTP(secret).now()
    assert verify_totp_code(secret, current_code) is True


def test_verify_totp_code_rejects_a_wrong_code():
    secret = generate_totp_secret()
    assert verify_totp_code(secret, "000000") is False


def test_generate_backup_codes_returns_the_expected_count_and_shape():
    codes = generate_backup_codes()
    assert len(codes) == BACKUP_CODE_COUNT
    assert len(set(codes)) == BACKUP_CODE_COUNT  # all unique
    for code in codes:
        assert "-" in code


def test_consume_backup_code_matches_and_removes_the_used_code():
    codes = generate_backup_codes()
    hashed = hash_backup_codes(codes)

    remaining = consume_backup_code(hashed, codes[0])

    assert remaining is not None
    assert len(remaining) == len(hashed) - 1


def test_consume_backup_code_returns_none_for_an_unknown_code():
    codes = generate_backup_codes()
    hashed = hash_backup_codes(codes)

    assert consume_backup_code(hashed, "not-a-real-code") is None


def test_consumed_backup_code_cannot_be_reused():
    codes = generate_backup_codes()
    hashed = hash_backup_codes(codes)

    remaining = consume_backup_code(hashed, codes[0])
    assert consume_backup_code(remaining, codes[0]) is None
