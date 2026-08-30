"""
Postcode-radius search: "degree-relevant local businesses within N miles of
my campus." Reuses two pieces already built elsewhere rather than
duplicating logic:

  - Safeguarding: only businesses with an APPROVED UniversityBusinessAgreement
    covering the student's band are eligible at all (see access_control.py's
    reasoning — this endpoint is just another surface the same rule applies to).
  - Degree relevance: the same strong/supporting keyword scorer used inside
    the matching engine (app/services/matching/degree.py), so "relevant to
    your degree" means the same thing here as it does in your project feed.
"""
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.deps import require_student
from app.db.session import get_db
from app.models.enums import AgreementStatus
from app.models.policy import UniversityBusinessAgreement
from app.models.university import University
from app.models.user import BusinessProfile, StudentProfile, User
from app.schemas.local_search import LocalBusinessResult, LocalSearchMeta
from app.services.geo import haversine_distance_miles
from app.services.matching.degree import degree_relevance_score

router = APIRouter(tags=["local-search"])


@router.get("/universities/{university_id}/local-businesses", response_model=list[LocalBusinessResult])
def get_local_businesses(
    university_id: str,
    radius_miles: float = Query(10.0, ge=0.5, le=100, description="Search radius around the campus, in miles"),
    min_degree_relevance: float = Query(
        0.0, ge=0.0, le=1.0,
        description="Filter out businesses below this degree-relevance score (0 = show all approved businesses in range)",
    ),
    db: Session = Depends(get_db),
    student_user: User = Depends(require_student),
):
    """
    Students only ever search around their OWN campus — this isn't a
    general-purpose business directory, it's scoped to the safeguarding
    agreements that already exist for this student's university.
    """
    if student_user.university_id != university_id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "You can only search local businesses for your own university")

    university = db.query(University).filter(University.id == university_id).first()
    if university is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "University not found")
    if university.latitude is None or university.longitude is None:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "This university's campus location hasn't been set yet — ask your careers team to add a campus postcode",
        )

    student = db.query(StudentProfile).filter(StudentProfile.user_id == student_user.id).first()
    assert student is not None, "require_student guarantees a StudentProfile row exists"

    # Safeguarding gate, same as everywhere else: only APPROVED agreements
    # that cover this student's band make a business eligible at all.
    approved_agreements = (
        db.query(UniversityBusinessAgreement)
        .filter(
            UniversityBusinessAgreement.university_id == university_id,
            UniversityBusinessAgreement.status == AgreementStatus.APPROVED,
        )
        .all()
    )
    eligible_agreements = {
        a.business_id: a for a in approved_agreements if student.band.value in a.allowed_bands
    }
    if not eligible_agreements:
        return []

    businesses = (
        db.query(BusinessProfile)
        .filter(BusinessProfile.id.in_(eligible_agreements.keys()))
        .filter(BusinessProfile.latitude.isnot(None), BusinessProfile.longitude.isnot(None))
        .all()
    )

    results: list[LocalBusinessResult] = []
    for business in businesses:
        # Already filtered to latitude/longitude IS NOT NULL in the query above.
        assert business.latitude is not None and business.longitude is not None
        distance = haversine_distance_miles(
            university.latitude, university.longitude, business.latitude, business.longitude
        )
        if distance > radius_miles:
            continue

        agreement = eligible_agreements[business.id]

        # A business may be approved for several categories — surface the
        # single MOST relevant one to this student's degree, since that's
        # what "degree relevant" in the feature name actually means to a
        # student scanning a list, not an average across unrelated categories.
        best_score, best_label = 0.0, "General relevance"
        for category_value in agreement.allowed_categories:
            score, keyword = degree_relevance_score(student.degree_title, category_value)
            if score > best_score:
                best_score = score
                best_label = keyword or category_value.replace("_", " ").title()

        if best_score < min_degree_relevance:
            continue

        results.append(
            LocalBusinessResult(
                business_id=business.id,
                company_name=business.company_name,
                industry=business.industry,
                postcode=business.postcode,
                distance_miles=round(distance, 1),
                degree_relevance_score=round(best_score, 2),
                degree_relevance_label=best_label,
                approved_categories=agreement.allowed_categories,
                average_rating=business.average_rating,
                completed_projects_count=business.completed_projects_count,
            )
        )

    # Degree relevance first (a highly-relevant business 8 miles away beats
    # a barely-relevant one 2 miles away), proximity as the tiebreaker.
    results.sort(key=lambda r: (-r.degree_relevance_score, r.distance_miles))
    return results


@router.get("/universities/{university_id}/local-businesses/meta", response_model=LocalSearchMeta)
def get_local_search_meta(
    university_id: str,
    radius_miles: float = Query(10.0, ge=0.5, le=100),
    db: Session = Depends(get_db),
    student_user: User = Depends(require_student),
):
    """Small companion endpoint so the UI can show 'X results within Y miles
    of {campus}' without recomputing the full search just for the header."""
    if student_user.university_id != university_id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "You can only search local businesses for your own university")

    university = db.query(University).filter(University.id == university_id).first()
    if university is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "University not found")

    results = get_local_businesses(university_id, radius_miles, 0.0, db, student_user)
    return LocalSearchMeta(
        campus_name=university.name,
        campus_postcode=university.postcode,
        radius_miles=radius_miles,
        total_results=len(results),
    )
