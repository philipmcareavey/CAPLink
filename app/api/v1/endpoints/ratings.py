from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.contract import Contract
from app.models.enums import RatingVisibility
from app.models.rating import Rating
from app.models.user import BusinessProfile, StudentProfile, User
from app.schemas.rating import RatingCreate, RatingHistoryEntry, RatingOut
from app.services.notifications import notify_from_template

router = APIRouter(prefix="/ratings", tags=["ratings"])


def _other_party_user_id(db: Session, contract: Contract, rater: User) -> str:
    student_user_id = db.query(StudentProfile.user_id).filter(StudentProfile.id == contract.student_id).scalar()
    business_user_id = db.query(BusinessProfile.user_id).filter(BusinessProfile.id == contract.business_id).scalar()
    return business_user_id if rater.id == student_user_id else student_user_id


def _recompute_reputation(db: Session, ratee_user_id: str) -> None:
    """Recalculate the denormalised average_rating fields after a release."""
    released = (
        db.query(Rating)
        .filter(Rating.ratee_user_id == ratee_user_id, Rating.is_released == True)  # noqa: E712
        .all()
    )
    if not released:
        return
    avg = sum(r.overall_score for r in released) / len(released)

    student = db.query(StudentProfile).filter(StudentProfile.user_id == ratee_user_id).first()
    if student:
        student.average_rating = round(avg, 2)
        student.completed_projects_count = len(released)
        db.commit()
        return

    business = db.query(BusinessProfile).filter(BusinessProfile.user_id == ratee_user_id).first()
    if business:
        business.average_rating = round(avg, 2)
        business.completed_projects_count = len(released)
        db.commit()


@router.post("", response_model=RatingOut, status_code=status.HTTP_201_CREATED)
def submit_rating(payload: RatingCreate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    contract = db.query(Contract).filter(Contract.id == payload.contract_id).first()
    if contract is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Contract not found")

    existing = (
        db.query(Rating)
        .filter(Rating.contract_id == contract.id, Rating.rater_user_id == user.id)
        .first()
    )
    if existing:
        raise HTTPException(status.HTTP_409_CONFLICT, "You've already rated this contract")

    ratee_id = _other_party_user_id(db, contract, user)

    rating = Rating(
        contract_id=contract.id,
        rater_user_id=user.id,
        ratee_user_id=ratee_id,
        overall_score=payload.overall_score,
        sub_scores=payload.sub_scores,
        private_comment=payload.private_comment,
        visibility=payload.visibility,
    )
    db.add(rating)
    db.flush()

    # Blind-until-both-submit: check if the other side has already rated.
    counterpart = (
        db.query(Rating)
        .filter(Rating.contract_id == contract.id, Rating.rater_user_id == ratee_id)
        .first()
    )
    if counterpart is not None:
        rating.is_released = True
        counterpart.is_released = True
        db.commit()
        _recompute_reputation(db, ratee_id)
        _recompute_reputation(db, user.id)
        notify_from_template(db, ratee_id, "rating_released")
        notify_from_template(db, user.id, "rating_released")
    else:
        db.commit()

    db.refresh(rating)
    return rating


@router.get("/pending", response_model=list[RatingOut])
def my_pending_ratings(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """Ratings the user has submitted that are still waiting on the other side."""
    return (
        db.query(Rating)
        .filter(Rating.rater_user_id == user.id, Rating.is_released == False)  # noqa: E712
        .all()
    )


@router.get("/mine", response_model=list[RatingHistoryEntry])
def my_rating_history(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """Full history, both directions."""
    ratings = (
        db.query(Rating)
        .filter((Rating.rater_user_id == user.id) | (Rating.ratee_user_id == user.id))
        .order_by(Rating.created_at.desc())
        .all()
    )

    results = []
    for rating in ratings:
        given = rating.rater_user_id == user.id
        reveal = given or rating.is_released
        results.append(
            RatingHistoryEntry(
                id=rating.id,
                contract_id=rating.contract_id,
                counterpart_user_id=rating.ratee_user_id if given else rating.rater_user_id,
                direction="given" if given else "received",
                is_released=rating.is_released,
                overall_score=rating.overall_score if reveal else None,
                sub_scores=rating.sub_scores if reveal else None,
                visibility=rating.visibility,
            )
        )
    return results
