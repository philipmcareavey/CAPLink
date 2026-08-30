from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import require_student
from app.db.session import get_db
from app.models.recommendation import RecommendationLog
from app.models.user import StudentProfile, User

router = APIRouter(prefix="/recommendations", tags=["recommendations"])


class RecommendationFeedback(BaseModel):
    action_taken: str  # "applied" | "dismissed" | "messaged"


@router.post("/{log_id}/feedback", status_code=status.HTTP_204_NO_CONTENT)
def record_feedback(log_id: str, payload: RecommendationFeedback, db: Session = Depends(get_db)):
    """
    Every recommendation shown carries a log_id. Clients call this when the
    user acts on (or dismisses) it — this is the implicit-feedback signal
    that powers Phase 2/3 of the matching engine (collaborative filtering /
    embeddings), per the implementation plan.
    """
    log = db.query(RecommendationLog).filter(RecommendationLog.id == log_id).first()
    if log is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Recommendation log not found")
    log.action_taken = payload.action_taken
    db.commit()


class EmployerSuggestion(BaseModel):
    employer_type: str
    reason: str


# Simplified, explainable stand-in for the "career/employer suggestions"
# feature in the plan (Phase 4). In production this reads aggregated,
# anonymised outcome data instead of a static lookup.
_EMPLOYER_SUGGESTION_RULES = [
    (["python", "sql", "statistics"], "Early-stage analytics consultancies",
     "Students with a stats + Python profile succeed here at a notably higher rate"),
    (["figma", "marketing"], "Brand & marketing agencies",
     "High demand for portfolio-backed marketing/design work matching your modules"),
    (["javascript", "react"], "Product-led software startups",
     "Frontend skills are in consistent demand for short build/fix engagements"),
]


@router.get("/employer-suggestions", response_model=list[EmployerSuggestion])
def get_employer_suggestions(db: Session = Depends(get_db), student_user: User = Depends(require_student)):
    student = db.query(StudentProfile).filter(StudentProfile.user_id == student_user.id).first()
    assert student is not None, "require_student guarantees a StudentProfile row exists"
    student_skills = {s.lower() for s in student.skills}

    suggestions = []
    for keywords, employer_type, reason in _EMPLOYER_SUGGESTION_RULES:
        if any(k in student_skills for k in keywords):
            suggestions.append(EmployerSuggestion(employer_type=employer_type, reason=reason))
    return suggestions
