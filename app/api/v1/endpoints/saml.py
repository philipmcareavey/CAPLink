"""
University SAML SSO flow endpoints (Technical Implementation Plan 2.b).
Admin configuration (setting/uploading a university's IdP details) lives in
universities.py instead — this file is only the actual SSO dance: metadata,
SP-initiated login, and the assertion consumer service (ACS).
"""
import secrets

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import RedirectResponse, Response
from onelogin.saml2.auth import OneLogin_Saml2_Auth
from onelogin.saml2.settings import OneLogin_Saml2_Settings
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import create_access_token, create_refresh_token, hash_password
from app.db.session import get_db
from app.models.enums import StudentBand, UserRole
from app.models.university import University
from app.models.user import StudentProfile, User
from app.services import saml as saml_service

router = APIRouter(prefix="/auth/saml", tags=["saml-sso"])

SAML_BASE_URL = f"{settings.PUBLIC_APP_URL}/api/v1/auth/saml"


def _get_university_or_404(slug: str, db: Session) -> University:
    university = db.query(University).filter(University.slug == slug).first()
    if university is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Unknown university")
    return university


def _error_redirect(reason: str) -> RedirectResponse:
    # Deliberately generic in the URL — internal exception text never
    # reaches the browser's address bar/history.
    return RedirectResponse(f"{settings.PUBLIC_APP_URL}/app/app.html#sso_error={reason}", status_code=302)


@router.get("/{slug}/metadata")
def saml_metadata(slug: str, db: Session = Depends(get_db)):
    """SP metadata for this university's IT team to consume when setting up
    the trust relationship on their end — deliberately works even before
    saml_idp_* is configured (sp_validation_only=True below), since a
    university typically needs to hand this over *before* they hand back
    their own IdP details."""
    university = _get_university_or_404(slug, db)
    settings_dict = saml_service.build_settings(university, SAML_BASE_URL)
    saml_settings = OneLogin_Saml2_Settings(settings_dict, sp_validation_only=True)
    metadata = saml_settings.get_sp_metadata()
    errors = saml_settings.validate_metadata(metadata)
    if errors:
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, f"Invalid SP metadata: {errors}")
    return Response(content=metadata, media_type="application/xml")


@router.get("/{slug}/login")
async def saml_login(slug: str, request: Request, db: Session = Depends(get_db)):
    """SP-initiated login — redirects the browser to this university's IdP.
    2.b.iii: this is a separate, additive path — /auth/login is completely
    untouched, so a university with saml_enabled=False just never has
    anyone hit this route."""
    university = _get_university_or_404(slug, db)
    if not university.saml_enabled:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "SSO is not enabled for this university")

    settings_dict = saml_service.build_settings(university, SAML_BASE_URL)
    req_data = await saml_service.build_request_data(request)
    auth = OneLogin_Saml2_Auth(req_data, settings_dict)
    return RedirectResponse(auth.login(), status_code=302)


@router.post("/{slug}/acs")
async def saml_acs(slug: str, request: Request, db: Session = Depends(get_db)):
    """Assertion Consumer Service — the IdP POSTs the SAML response here
    after the user authenticates. On success, redirects the browser back to
    the reference app with fresh CAPLink tokens in the URL *fragment* (never
    the query string or a log line) — see static/app/js/main.js's
    consumeSsoHandoff(), which is what actually reads them back out."""
    university = _get_university_or_404(slug, db)
    if not university.saml_enabled:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "SSO is not enabled for this university")

    settings_dict = saml_service.build_settings(university, SAML_BASE_URL)
    req_data = await saml_service.build_request_data(request)
    auth = OneLogin_Saml2_Auth(req_data, settings_dict)
    auth.process_response()

    if auth.get_errors() or not auth.is_authenticated():
        return _error_redirect("assertion_invalid")

    mapped = saml_service.map_attributes(auth.get_attributes(), university.saml_attribute_mapping)
    email = mapped["email"] or auth.get_nameid()
    if not email:
        return _error_redirect("no_email_in_assertion")

    role = saml_service.infer_role(mapped["affiliation"])

    user = db.query(User).filter(User.email == email).first()
    if user is not None:
        # Existing account: SSO can only ever authenticate as whatever role
        # that account already legitimately has, at whatever university
        # it's actually tied to — never used to escalate or reassign either.
        if user.university_id != university.id or user.role not in (UserRole.STUDENT, UserRole.UNIVERSITY_ADMIN):
            return _error_redirect("account_mismatch")
        if not user.is_active:
            return _error_redirect("account_disabled")
    elif role == UserRole.UNIVERSITY_ADMIN:
        # Deliberate safety rule, not a missing feature: SSO never
        # auto-creates a UNIVERSITY_ADMIN account just because an IdP's
        # affiliation attribute says "staff". Admin access controls which
        # businesses can reach a university's students at all (the core
        # safeguarding gate this whole platform is built around) — that
        # privilege needs a human decision, not an IdP claim, the first
        # time it's granted. Once an admin account exists, SSO logs into
        # it fine (the branch above).
        return _error_redirect("admin_account_not_provisioned")
    else:
        # JIT-provision a new student — this is the safe, intended case
        # SSO exists for. is_email_verified=True: a successful signed SAML
        # assertion from the university's own IdP *is* the verification,
        # stronger than the confirmation-link flow it stands in for here.
        user = User(
            email=email,
            hashed_password=hash_password(secrets.token_urlsafe(32)),  # never used to log in directly
            role=UserRole.STUDENT,
            full_name=mapped["full_name"] or email,
            university_id=university.id,
            is_email_verified=True,
        )
        db.add(user)
        db.flush()
        band = mapped["band"] if mapped["band"] in {b.value for b in StudentBand} else saml_service.DEFAULT_JIT_BAND
        db.add(
            StudentProfile(
                user_id=user.id,
                university_id=university.id,
                degree_title=mapped["degree_title"] or saml_service.PLACEHOLDER_DEGREE_TITLE,
                band=band,
            )
        )
        db.commit()
        db.refresh(user)

    # SSO bypasses CAPLink's own TOTP requirement even if the account has it
    # enabled: the trust model here is that the IdP already performed
    # whatever strong authentication it requires before issuing a signed
    # assertion — CAPLink doesn't second-guess a trusted IdP's own auth.
    access_token = create_access_token(user.id, user.role.value, user.university_id)
    refresh_token = create_refresh_token(user.id)
    return RedirectResponse(
        f"{settings.PUBLIC_APP_URL}/app/app.html#access_token={access_token}&refresh_token={refresh_token}",
        status_code=302,
    )
