import secrets
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Request, status
from jose import JWTError
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.config import settings
from app.core.rate_limit import limiter
from app.core.security import (
    create_access_token,
    create_mfa_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)
from app.db.session import get_db
from app.models.enums import UserRole
from app.models.university import University
from app.models.user import BusinessProfile, StudentProfile, User
from app.schemas.token import (
    MfaDisableRequest,
    MfaEnableRequest,
    MfaEnableResponse,
    MfaRequired,
    MfaSetupResponse,
    MfaVerifyRequest,
    RefreshRequest,
    TokenPair,
)
from app.schemas.user import (
    BusinessRegister,
    ChangePasswordRequest,
    LoginRequest,
    RegistrationResult,
    ResendVerificationRequest,
    StudentRegister,
)
from app.services import mfa as mfa_service
from app.services.account_lockout import is_locked, register_failed_attempt, register_successful_login
from app.services.captcha import verify_captcha
from app.services.email import send_verification_email
from app.services.password_policy import PasswordPolicyError, validate_password

router = APIRouter(prefix="/auth", tags=["auth"])

ADMIN_ROLES = (UserRole.UNIVERSITY_ADMIN, UserRole.PLATFORM_ADMIN)


def _issue_tokens(user: User) -> TokenPair:
    access = create_access_token(user.id, user.role.value, user.university_id)
    refresh = create_refresh_token(user.id)
    return TokenPair(access_token=access, refresh_token=refresh)


def _start_email_verification(user: User) -> None:
    """Generates a fresh token (invalidating any earlier one for this user
    — only the most recent link ever works) and sends it. Shared by
    registration and /resend-verification.

    Auto-verifies instead, in development only: no real ESP is wired up
    yet (app/services/email.py just logs), and this project has treated
    zero-friction local dev/demo usage as a hard requirement throughout
    its history — making the reference apps (static/app, static/demo)
    unusable for a fresh registration without digging a token out of a log
    line would violate that for no real security benefit locally. Staging
    and production still enforce the real flow."""
    if settings.ENVIRONMENT == "development":
        user.is_email_verified = True
        return
    user.email_verification_token = secrets.token_urlsafe(32)
    user.email_verification_token_expires_at = datetime.utcnow() + timedelta(
        hours=settings.EMAIL_VERIFICATION_TOKEN_EXPIRE_HOURS
    )
    send_verification_email(user.email, user.email_verification_token)


@router.get("/captcha-site-key")
def get_captcha_site_key():
    """Unauthenticated by design — a site key is meant to be embedded in
    public frontend HTML (Technical Implementation Plan 2.c.iii), same trust
    model as a Stripe publishable key. Lets the registration forms load
    whatever key is actually configured server-side (today: hCaptcha's own
    test key, see Settings.HCAPTCHA_SITE_KEY) without hardcoding it into the
    JS, so swapping in a real key later is a pure config change."""
    return {"site_key": settings.HCAPTCHA_SITE_KEY}


@router.post(
    "/register/student", response_model=RegistrationResult | TokenPair, status_code=status.HTTP_201_CREATED
)
@limiter.limit("10/minute")
def register_student(request: Request, payload: StudentRegister, db: Session = Depends(get_db)):
    """Creates a student account, scoped to a university by email domain
    match. Returns tokens directly in development only; staging/production
    require clicking a real emailed verification link first."""
    if not verify_captcha(payload.captcha_token):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Captcha verification failed")

    university = db.query(University).filter(University.slug == payload.university_slug).first()
    if university is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Unknown university")
    if not university.is_license_active():
        raise HTTPException(status.HTTP_403_FORBIDDEN, "This university's CAPLink license is not currently active")

    if not payload.email.lower().endswith(f"@{university.domain.lower()}"):
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"Email must belong to the university's domain (@{university.domain}) to verify student status",
        )

    if db.query(User).filter(User.email == payload.email).first():
        raise HTTPException(status.HTTP_409_CONFLICT, "An account with this email already exists")

    try:
        validate_password(payload.password)
    except PasswordPolicyError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc))

    if not payload.data_sharing_consent:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "You must consent to sharing engagement/outcome data with your university to register.",
        )

    # Domain match still confirms *which* university, but real verification
    # (2.a.iii) now needs an actual clicked link, not just an email suffix.
    user = User(
        email=payload.email,
        hashed_password=hash_password(payload.password),
        role=UserRole.STUDENT,
        full_name=payload.full_name,
        university_id=university.id,
        is_email_verified=False,
    )
    db.add(user)
    db.flush()

    profile = StudentProfile(
        user_id=user.id,
        university_id=university.id,
        degree_title=payload.degree_title,
        band=payload.band,
        data_sharing_consent_at=datetime.utcnow(),
    )
    db.add(profile)
    _start_email_verification(user)
    db.commit()
    if settings.ENVIRONMENT == "development":
        db.refresh(user)
        return _issue_tokens(user)
    return RegistrationResult()


@router.post(
    "/register/business", response_model=RegistrationResult | TokenPair, status_code=status.HTTP_201_CREATED
)
@limiter.limit("10/minute")
def register_business(request: Request, payload: BusinessRegister, db: Session = Depends(get_db)):
    """Creates a business account with zero visibility of any student until
    a university approves a partnership agreement — see the safeguarding
    model in the top-level README. Same dev/staging verification split as
    student registration."""
    if not verify_captcha(payload.captcha_token):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Captcha verification failed")

    if db.query(User).filter(User.email == payload.email).first():
        raise HTTPException(status.HTTP_409_CONFLICT, "An account with this email already exists")

    try:
        validate_password(payload.password)
    except PasswordPolicyError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc))

    user = User(
        email=payload.email,
        hashed_password=hash_password(payload.password),
        role=UserRole.BUSINESS,
        full_name=payload.full_name,
        is_email_verified=False,
    )
    db.add(user)
    db.flush()

    profile = BusinessProfile(
        user_id=user.id,
        company_name=payload.company_name,
        company_registration_number=payload.company_registration_number,
        industry=payload.industry,
    )
    db.add(profile)
    _start_email_verification(user)
    db.commit()
    if settings.ENVIRONMENT == "development":
        db.refresh(user)
        return _issue_tokens(user)
    return RegistrationResult()


@router.get("/verify-email")
def verify_email(token: str, db: Session = Depends(get_db)):
    """The link a user clicks from their verification email. A no-op in
    development, where registration auto-verifies instead."""
    user = db.query(User).filter(User.email_verification_token == token).first()
    if (
        user is None
        or user.email_verification_token_expires_at is None
        or user.email_verification_token_expires_at < datetime.utcnow()
    ):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Invalid or expired verification link")

    user.is_email_verified = True
    user.email_verification_token = None
    user.email_verification_token_expires_at = None
    db.commit()
    return {"message": "Email verified — you can now log in."}


@router.post("/resend-verification")
@limiter.limit("5/minute")
def resend_verification(request: Request, payload: ResendVerificationRequest, db: Session = Depends(get_db)):
    """Always returns the same message regardless of whether the email
    exists or is already verified — otherwise this becomes a free oracle
    for probing which emails have accounts."""
    user = db.query(User).filter(User.email == payload.email).first()
    # Same response whether or not the account exists/is already verified —
    # otherwise this endpoint becomes a free "does this email have an
    # account, and is it verified" oracle for anyone who tries it.
    if user is not None and not user.is_email_verified:
        _start_email_verification(user)
        db.commit()
    return {"message": "If that email has an unverified account, a new verification link has been sent."}


@router.post("/login", response_model=TokenPair | MfaRequired)
@limiter.limit("10/minute")
def login(request: Request, payload: LoginRequest, db: Session = Depends(get_db)):
    """Returns a real token pair, or — for an MFA-enabled admin — a
    short-lived `mfa` challenge token to exchange at /auth/mfa/verify
    instead. Progressively locks the account after repeated failures
    (see app/services/account_lockout.py)."""
    user = db.query(User).filter(User.email == payload.email).first()
    if user is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Incorrect email or password")

    if is_locked(user):
        raise HTTPException(status.HTTP_423_LOCKED, "Too many failed login attempts — try again later.")

    if not verify_password(payload.password, user.hashed_password):
        register_failed_attempt(user)
        db.commit()
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Incorrect email or password")

    if not user.is_active:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Account disabled")

    if not user.is_email_verified:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            "Please verify your email before logging in (see /auth/resend-verification if you need a new link).",
        )

    register_successful_login(user)
    db.commit()

    if user.role in ADMIN_ROLES and user.totp_enabled:
        return MfaRequired(mfa_token=create_mfa_token(user.id))
    return _issue_tokens(user)


@router.post("/mfa/verify", response_model=TokenPair)
@limiter.limit("10/minute")
def mfa_verify(request: Request, payload: MfaVerifyRequest, db: Session = Depends(get_db)):
    """Exchanges /auth/login's short-lived `mfa` challenge token plus a
    TOTP code (or a single-use backup code) for real access/refresh
    tokens."""
    try:
        decoded = decode_token(payload.mfa_token)
        if decoded.get("type") != "mfa":
            raise ValueError("wrong token type")
        user_id = decoded["sub"]
    except (JWTError, ValueError, KeyError):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid or expired MFA challenge — log in again")

    user = db.query(User).filter(User.id == user_id).first()
    if user is None or not user.totp_enabled or user.totp_secret is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid or expired MFA challenge — log in again")

    if mfa_service.verify_totp_code(user.totp_secret, payload.code):
        return _issue_tokens(user)

    remaining = mfa_service.consume_backup_code(user.mfa_backup_codes, payload.code)
    if remaining is not None:
        user.mfa_backup_codes = remaining
        db.commit()
        return _issue_tokens(user)

    raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Incorrect code")


@router.post("/mfa/setup", response_model=MfaSetupResponse)
def mfa_setup(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """Persists the new secret onto the account immediately, same as every
    real-world TOTP setup flow (GitHub, Google, ...) — it just isn't
    *enforced* (totp_enabled stays False) until /mfa/enable confirms the
    admin can actually generate valid codes with it. Calling this again
    before enabling simply replaces the pending secret, which is fine:
    nothing is enforced yet either way."""
    secret = mfa_service.generate_totp_secret()
    user.totp_secret = secret
    db.commit()
    return MfaSetupResponse(secret=secret, provisioning_uri=mfa_service.provisioning_uri(secret, user.email))


@router.post("/mfa/enable", response_model=MfaEnableResponse)
def mfa_enable(payload: MfaEnableRequest, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """Confirms the account can actually generate a valid code with the
    secret from /auth/mfa/setup, then genuinely turns MFA on and issues
    8 single-use backup codes — shown to the user exactly once."""
    if user.totp_secret is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Call /auth/mfa/setup first")
    if not mfa_service.verify_totp_code(user.totp_secret, payload.code):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Incorrect code")

    backup_codes = mfa_service.generate_backup_codes()
    user.mfa_backup_codes = mfa_service.hash_backup_codes(backup_codes)
    user.totp_enabled = True
    db.commit()
    return MfaEnableResponse(backup_codes=backup_codes)


@router.post("/mfa/disable")
def mfa_disable(payload: MfaDisableRequest, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """Requires a current, valid TOTP code to turn MFA off — otherwise a
    hijacked access token alone would be enough to strip an admin account's
    second factor, defeating the point of having one."""
    if not user.totp_enabled or user.totp_secret is None or not mfa_service.verify_totp_code(
        user.totp_secret, payload.code
    ):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Incorrect code")

    user.totp_enabled = False
    user.totp_secret = None
    user.mfa_backup_codes = []
    db.commit()
    return {"message": "MFA disabled."}


@router.post("/change-password")
def change_password(
    payload: ChangePasswordRequest, db: Session = Depends(get_db), user: User = Depends(get_current_user)
):
    """Requires the current password and re-runs the full password policy
    (complexity + HaveIBeenPwned breach check) on the new one."""
    if not verify_password(payload.current_password, user.hashed_password):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Current password is incorrect")
    try:
        validate_password(payload.new_password)
    except PasswordPolicyError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc))

    user.hashed_password = hash_password(payload.new_password)
    db.commit()
    return {"message": "Password changed."}


@router.post("/refresh", response_model=TokenPair)
def refresh_token(payload: RefreshRequest, db: Session = Depends(get_db)):
    """
    Mobile apps call this with the long-lived refresh token (kept in secure
    device storage) to silently mint a new short-lived access token, instead
    of forcing the user to log in again every 30 minutes.
    """
    try:
        decoded = decode_token(payload.refresh_token)
        if decoded.get("type") != "refresh":
            raise ValueError("wrong token type")
        user_id = decoded["sub"]
    except (JWTError, ValueError, KeyError):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid refresh token")

    user = db.query(User).filter(User.id == user_id).first()
    if user is None or not user.is_active:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid refresh token")
    return _issue_tokens(user)
