from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.security import verify_password
from app.db.session import get_db
from app.models.user import User
from app.services.privacy import anonymize_user_account, export_user_data

router = APIRouter(prefix="/privacy", tags=["privacy"])


@router.get("/export")
def export_my_data(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """Technical Implementation Plan 7.c.i — self-service GDPR Subject
    Access Request export. Everything CAPLink holds on this account, as
    plain JSON; see app/services/privacy.py::export_user_data for exactly
    what's included and why."""
    return export_user_data(db, user)


class AccountDeletionRequest(BaseModel):
    current_password: str


@router.delete("/account", status_code=status.HTTP_200_OK)
def delete_my_account(
    payload: AccountDeletionRequest, db: Session = Depends(get_db), user: User = Depends(get_current_user)
):
    """Technical Implementation Plan 7.c.ii. Requires the current password
    — same "sensitive action needs reauth" pattern as MFA disable
    requiring a valid TOTP code — so a hijacked access token alone can't
    be used to destroy an account. See app/services/privacy.py's module
    docstring for why this anonymizes rather than hard-deletes."""
    if not verify_password(payload.current_password, user.hashed_password):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Current password is incorrect")

    anonymize_user_account(db, user)
    db.commit()
    return {"message": "Your account has been deleted and personal data anonymized."}
