from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.device import Device
from app.models.enums import UserRole
from app.models.recommendation import RecommendationLog
from app.models.user import BusinessProfile, StudentProfile, User
from app.schemas.device import DeviceRegister

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
