from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.device import Device
from app.models.enums import UserRole
from app.models.recommendation import RecommendationLog
from app.models.user import BusinessProfile, StudentProfile, User
from app.schemas.device import DeviceRegister
from app.schemas.notification_preferences import (
    NotificationPreferenceItem,
    NotificationPreferencesOut,
    NotificationPreferencesUpdate,
)
from app.services.notifications import NOTIFICATION_TEMPLATES

router = APIRouter(prefix="/mobile", tags=["mobile"])


@router.post("/devices", status_code=status.HTTP_201_CREATED)
def register_device(payload: DeviceRegister, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """
    Call this once after login/app-open on iOS/Android so push notifications
    (new matches, messages, milestone payments, ratings) can reach the
    device. Re-registering the same token is safe/idempotent.
    """
    existing = db.query(Device).filter(Device.push_token == payload.push_token).first()
    if existing:
        existing.user_id = user.id
        existing.platform = payload.platform
        existing.app_version = payload.app_version
        existing.is_active = True
        db.commit()
        return {"status": "updated", "device_id": existing.id}

    device = Device(
        user_id=user.id,
        platform=payload.platform,
        push_token=payload.push_token,
        app_version=payload.app_version,
    )
    db.add(device)
    db.commit()
    db.refresh(device)
    return {"status": "registered", "device_id": device.id}


@router.delete("/devices/{push_token}", status_code=status.HTTP_204_NO_CONTENT)
def deregister_device(push_token: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """Call on logout so a shared/reset device stops receiving this user's pushes."""
    db.query(Device).filter(Device.push_token == push_token, Device.user_id == user.id).delete()
    db.commit()


@router.get("/home")
def mobile_home(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """
    A single combined, trimmed-down payload for the mobile app's home
    screen — avoids the 4-5 separate round trips a web dashboard might make,
    which matters more on cellular connections. Returns only summary counts
    and the top few items; full lists still use the paginated feed/shortlist
    endpoints.
    """
    if user.role == UserRole.STUDENT:
        student = db.query(StudentProfile).filter(StudentProfile.user_id == user.id).first()
        unseen_recs = (
            db.query(RecommendationLog)
            .filter(RecommendationLog.user_id == user.id, RecommendationLog.action_taken.is_(None))
            .count()
        )
        return {
            "role": "student",
            "average_rating": student.average_rating if student else None,
            "completed_projects": student.completed_projects_count if student else 0,
            "new_suggestions_count": unseen_recs,
        }

    if user.role == UserRole.BUSINESS:
        business = db.query(BusinessProfile).filter(BusinessProfile.user_id == user.id).first()
        return {
            "role": "business",
            "average_rating": business.average_rating if business else None,
            "completed_projects": business.completed_projects_count if business else 0,
            "trust_tier": business.global_trust_tier.value if business else None,
        }

    return {"role": user.role.value}


@router.get("/notification-preferences", response_model=NotificationPreferencesOut)
def get_notification_preferences(user: User = Depends(get_current_user)):
    """Which push notification types this user currently receives."""
    return NotificationPreferencesOut(
        preferences=[
            NotificationPreferenceItem(
                template_key=key,
                label=title,
                enabled=key not in user.notification_opt_outs,
            )
            for key, (title, _body) in NOTIFICATION_TEMPLATES.items()
        ]
    )


@router.patch("/notification-preferences", response_model=NotificationPreferencesOut)
def update_notification_preferences(
    payload: NotificationPreferencesUpdate, db: Session = Depends(get_db), user: User = Depends(get_current_user)
):
    """Replaces the full set of muted notification types with `opted_out`."""
    unknown = set(payload.opted_out) - set(NOTIFICATION_TEMPLATES.keys())
    if unknown:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"Unknown notification type(s): {sorted(unknown)}")
    user.notification_opt_outs = payload.opted_out
    db.commit()
    return NotificationPreferencesOut(
        preferences=[
            NotificationPreferenceItem(template_key=key, label=title, enabled=key not in user.notification_opt_outs)
            for key, (title, _body) in NOTIFICATION_TEMPLATES.items()
        ]
    )
