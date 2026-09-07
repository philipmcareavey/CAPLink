"""
Data Subject Rights tooling (Technical Implementation Plan 7.c): a
self-service personal-data export (7.c.i, GDPR Subject Access Requests)
and a correctly-cascading account-deletion flow (7.c.ii).

Deletion here means ANONYMIZATION, not a hard `DELETE FROM users`, and
that's a deliberate design decision worth understanding, not an
oversight: a contract, milestone, rating, or message a user was party to
also belongs — legitimately — to the *other* party's own record (their
own contract history, their own received rating, their own conversation).
Hard-deleting the User row would either cascade-destroy the other party's
legitimate records too, or violate a foreign key and simply fail
outright. GDPR's right to erasure (Article 17) does not require deleting
data another party has a legitimate ongoing interest in keeping; it
requires erasing what identifies *this* person specifically. So
anonymization clears every field that identifies the requester
personally (email, name, password, MFA secrets, device push tokens,
portfolio links) while leaving the structural/transactional rows
(contracts, ratings, messages) intact but now pointing at an anonymized
account.
"""
import logging
import secrets
from datetime import datetime

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.models.application import Application
from app.models.contract import Contract
from app.models.device import Device
from app.models.message import Message, MessageThread
from app.models.rating import Rating
from app.models.recommendation import RecommendationLog
from app.models.user import BusinessProfile, StudentProfile, User

logger = logging.getLogger("caplink.privacy")


def export_user_data(db: Session, user: User) -> dict:
    """Everything CAPLink holds that constitutes this user's personal data
    or data processed in relation to them — a GDPR Subject Access Request
    export. Deliberately includes both sides of a conversation/rating the
    user is part of (they're entitled to what they sent AND what they
    received), not just rows where they're literally the row owner."""
    data: dict = {
        "account": {
            "id": user.id,
            "email": user.email,
            "full_name": user.full_name,
            "role": user.role.value,
            "is_email_verified": user.is_email_verified,
            "university_id": user.university_id,
            "created_at": user.created_at.isoformat(),
            "last_login_at": user.last_login_at.isoformat() if user.last_login_at else None,
        }
    }

    student = db.query(StudentProfile).filter(StudentProfile.user_id == user.id).first()
    if student is not None:
        data["student_profile"] = {
            "degree_title": student.degree_title,
            "band": student.band.value,
            "modules": student.modules,
            "skills": student.skills,
            "portfolio_urls": student.portfolio_urls,
            "hourly_rate_expectation_gbp": student.hourly_rate_expectation_gbp,
            "weekly_hours_available": student.weekly_hours_available,
            "right_to_work_confirmed": student.right_to_work_confirmed,
            "visa_weekly_hour_cap": student.visa_weekly_hour_cap,
            "average_rating": student.average_rating,
            "completed_projects_count": student.completed_projects_count,
            "data_sharing_consent_at": (
                student.data_sharing_consent_at.isoformat() if student.data_sharing_consent_at else None
            ),
        }
        data["applications"] = [
            {
                "project_id": a.project_id,
                "cover_note": a.cover_note,
                "proposed_rate_gbp": a.proposed_rate_gbp,
                "status": a.status.value,
                "created_at": a.created_at.isoformat(),
            }
            for a in db.query(Application).filter(Application.student_id == student.id).all()
        ]

    business = db.query(BusinessProfile).filter(BusinessProfile.user_id == user.id).first()
    if business is not None:
        data["business_profile"] = {
            "company_name": business.company_name,
            "company_registration_number": business.company_registration_number,
            "industry": business.industry,
            "company_size": business.company_size,
            "website": business.website,
            "description": business.description,
            "postcode": business.postcode,
            "average_rating": business.average_rating,
            "completed_projects_count": business.completed_projects_count,
        }

    contract_filters = []
    if student is not None:
        contract_filters.append(Contract.student_id == student.id)
    if business is not None:
        contract_filters.append(Contract.business_id == business.id)
    contracts = []
    if contract_filters:
        contracts = db.query(Contract).filter(or_(*contract_filters)).all()
    data["contracts"] = [
        {
            "id": c.id,
            "project_id": c.project_id,
            "status": c.status.value,
            "payment_rail": c.payment_rail.value,
            "milestones": [
                {"description": m.description, "payment_amount_gbp": m.payment_amount_gbp, "status": m.status.value}
                for m in c.milestones
            ],
        }
        for c in contracts
    ]

    threads = (
        db.query(MessageThread)
        .filter((MessageThread.student_user_id == user.id) | (MessageThread.business_user_id == user.id))
        .all()
    )
    thread_ids = [t.id for t in threads]
    data["messages"] = [
        {
            "thread_id": m.thread_id,
            "sent_by_you": m.sender_user_id == user.id,
            "content": m.content,
            "is_flagged": m.is_flagged,
            "created_at": m.created_at.isoformat(),
        }
        for m in db.query(Message).filter(Message.thread_id.in_(thread_ids)).all()
    ] if thread_ids else []

    data["ratings_given"] = [
        {"contract_id": r.contract_id, "overall_score": r.overall_score, "sub_scores": r.sub_scores}
        for r in db.query(Rating).filter(Rating.rater_user_id == user.id).all()
    ]
    data["ratings_received"] = [
        {
            "contract_id": r.contract_id,
            "overall_score": r.overall_score if r.is_released else None,
            "is_released": r.is_released,
        }
        for r in db.query(Rating).filter(Rating.ratee_user_id == user.id).all()
    ]

    data["recommendation_history"] = [
        {
            "entity_type": rl.entity_type,
            "entity_id": rl.entity_id,
            "score": rl.score,
            "reasons": rl.reasons,
            "action_taken": rl.action_taken,
            "created_at": rl.created_at.isoformat(),
        }
        for rl in db.query(RecommendationLog).filter(RecommendationLog.user_id == user.id).all()
    ]

    data["devices"] = [
        {"platform": d.platform.value, "app_version": d.app_version, "is_active": d.is_active}
        for d in db.query(Device).filter(Device.user_id == user.id).all()
    ]

    return data


def anonymize_user_account(db: Session, user: User) -> None:
    """Technical Implementation Plan 7.c.ii. See this module's docstring
    for why this anonymizes in place rather than deleting the User row.
    Callers are responsible for committing — this only mutates in-session
    objects."""
    anonymized_email = f"deleted-user-{user.id}@deleted.caplink.invalid"

    user.email = anonymized_email
    user.full_name = "Deleted User"
    user.hashed_password = hash_password(secrets.token_urlsafe(32))  # unusable — no one knows this value
    user.is_active = False
    user.totp_secret = None
    user.totp_enabled = False
    user.mfa_backup_codes = []
    user.email_verification_token = None
    user.email_verification_token_expires_at = None
    user.deleted_at = datetime.utcnow()

    student = db.query(StudentProfile).filter(StudentProfile.user_id == user.id).first()
    if student is not None:
        # Portfolio URLs are personal links (often a personal website/GitHub
        # tied to the student's real name) — cleared. degree_title/skills/
        # band are kept: not personally identifying on their own once
        # name/email are gone, and still needed for any contract's
        # legitimate ongoing record (the other party's history, dispute
        # evidence, platform-level reporting).
        student.portfolio_urls = []

    # Device push tokens identify a physical device — a lingering, genuinely
    # unnecessary piece of personal data once the account can no longer log
    # in at all. Hard-deleted, not just deactivated.
    db.query(Device).filter(Device.user_id == user.id).delete(synchronize_session=False)

    logger.info("account_anonymized", extra={"user_id": user.id})
