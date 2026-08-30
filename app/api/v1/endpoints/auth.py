from fastapi import APIRouter, Depends, HTTPException, status
from jose import JWTError
from sqlalchemy.orm import Session

from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)
from app.db.session import get_db
from app.models.enums import UserRole
from app.models.university import University
from app.models.user import BusinessProfile, StudentProfile, User
from app.schemas.token import RefreshRequest, TokenPair
from app.schemas.user import BusinessRegister, LoginRequest, StudentRegister

router = APIRouter(prefix="/auth", tags=["auth"])


def _issue_tokens(user: User) -> TokenPair:
    access = create_access_token(user.id, user.role.value, user.university_id)
    refresh = create_refresh_token(user.id)
    return TokenPair(access_token=access, refresh_token=refresh)


@router.post("/register/student", response_model=TokenPair, status_code=status.HTTP_201_CREATED)
def register_student(payload: StudentRegister, db: Session = Depends(get_db)):
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

    user = User(
        email=payload.email,
        hashed_password=hash_password(payload.password),
        role=UserRole.STUDENT,
        full_name=payload.full_name,
        university_id=university.id,
        is_email_verified=True,  # domain match is treated as verification for MVP
    )
    db.add(user)
    db.flush()

    profile = StudentProfile(
        user_id=user.id,
        university_id=university.id,
        degree_title=payload.degree_title,
        band=payload.band,
    )
    db.add(profile)
    db.commit()
    db.refresh(user)
    return _issue_tokens(user)


@router.post("/register/business", response_model=TokenPair, status_code=status.HTTP_201_CREATED)
def register_business(payload: BusinessRegister, db: Session = Depends(get_db)):
    if db.query(User).filter(User.email == payload.email).first():
        raise HTTPException(status.HTTP_409_CONFLICT, "An account with this email already exists")

    user = User(
        email=payload.email,
        hashed_password=hash_password(payload.password),
        role=UserRole.BUSINESS,
        full_name=payload.full_name,
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
    db.commit()
    db.refresh(user)
    return _issue_tokens(user)


@router.post("/login", response_model=TokenPair)
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == payload.email).first()
    if user is None or not verify_password(payload.password, user.hashed_password):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Incorrect email or password")
    if not user.is_active:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Account disabled")
    return _issue_tokens(user)


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
