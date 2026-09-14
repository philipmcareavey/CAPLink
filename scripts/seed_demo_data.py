"""
Seed script — wipes and rebuilds a small, realistic synthetic demo
dataset: 4 universities, ~80 students, 19 businesses (18 generated, each
with 1-3 university partnership agreements, plus one hand-crafted "hero"
business account — Northbridge Analytics, at the University of
Manchester), and ~25 projects. The hero's surrounding Manchester student
pool is engineered to produce a clearly differentiated shortlist once a
project brief is posted against it — see
caplink/docs/superpowers/specs/2026-09-13-demo-realism-matching-uplift-design.md.

Safe to rerun any time: always drops and recreates every table first, so
this never accumulates duplicates across repeated demo/pitch resets.
Deterministic (scripts.synthetic_data.RNG_SEED) — the same dataset every
run.

Run with:  python -m scripts.seed_demo_data
"""
import random
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.db.base_class import Base
from app.db.migrations import run_migrations
from app.db.session import SessionLocal, engine
from app.models.enums import (
    AgreementStatus,
    BusinessTrustTier,
    ProjectCategory,
    ProjectStatus,
    StudentBand,
    UniversityLicenseStatus,
    UniversityLicenseTier,
    UserRole,
)
from app.models.policy import UniversityBusinessAgreement
from app.models.project import Project
from app.models.university import University
from app.models.user import BusinessProfile, StudentProfile, User
from app.services import matching
from scripts import synthetic_data

import app.models  # noqa: F401

DEMO_PASSWORD = "ChangeMe123!"

# (name, slug, domain, postcode, lat, lon) — real, well-known campus
# coordinates used only illustratively (see the marketing site's own
# "Not affiliated with any university shown for illustration" footer note).
_UNIVERSITY_SEEDS = [
    ("University of Manchester", "manchester", "manchester.ac.uk", "M13 9PL", 53.4668, -2.2339),
    ("University of Leeds", "leeds", "leeds.ac.uk", "LS2 9JT", 53.8067, -1.5550),
    ("University of Sheffield", "sheffield", "sheffield.ac.uk", "S10 2TN", 53.3811, -1.4870),
    ("Manchester Metropolitan University", "manchester-met", "mmu.ac.uk", "M15 6BH", 53.4715, -2.2445),
]


@dataclass
class SeedSummary:
    universities: int
    students: int
    businesses: int
    projects: int
    hero_business_email: str
    hero_business_password: str


def _create_universities(db: Session) -> list[University]:
    universities = []
    for name, slug, domain, postcode, lat, lon in _UNIVERSITY_SEEDS:
        university = University(
            name=name, slug=slug, domain=domain, primary_color="#1B2A45",
            license_tier=UniversityLicenseTier.ENTERPRISE, license_status=UniversityLicenseStatus.ACTIVE,
            license_seats=5000, primary_contact_name="Careers & Employability Service",
            primary_contact_email=f"careers@{domain}", postcode=postcode, latitude=lat, longitude=lon,
        )
        db.add(university)
        universities.append(university)
    db.flush()
    return universities


def _create_admin(db: Session, university: University) -> User:
    admin = User(
        email=f"admin@{university.domain}", hashed_password=hash_password(DEMO_PASSWORD),
        role=UserRole.UNIVERSITY_ADMIN, full_name="Careers Service Admin",
        university_id=university.id, is_email_verified=True,
    )
    db.add(admin)
    return admin


def _create_student(db: Session, data: dict) -> StudentProfile:
    user = User(
        email=data["email"], hashed_password=hash_password(DEMO_PASSWORD), role=UserRole.STUDENT,
        full_name=data["full_name"], university_id=data["university_id"], is_email_verified=True,
    )
    db.add(user)
    db.flush()
    profile = StudentProfile(
        user_id=user.id, university_id=data["university_id"], degree_title=data["degree_title"],
        band=data["band"], data_sharing_consent_at=datetime.utcnow(), modules=data["modules"],
        skills=data["skills"], hourly_rate_expectation_gbp=data["hourly_rate_expectation_gbp"],
        weekly_hours_available=data["weekly_hours_available"], is_id_verified=data["is_id_verified"],
        average_rating=data["average_rating"], completed_projects_count=data["completed_projects_count"],
        on_time_rate=data["on_time_rate"],
    )
    matching.refresh_student_embedding(profile)
    db.add(profile)
    return profile


def _create_business(db: Session, data: dict, admin_by_university: dict[str, User]) -> BusinessProfile:
    user = User(
        email=data["email"], hashed_password=hash_password(DEMO_PASSWORD), role=UserRole.BUSINESS,
        full_name=data["full_name"], is_email_verified=True,
    )
    db.add(user)
    db.flush()
    business = BusinessProfile(
        user_id=user.id, company_name=data["company_name"], company_registration_number=data["company_registration_number"],
        industry=data["industry"], global_trust_tier=BusinessTrustTier.UNIVERSITY_APPROVED, is_registration_verified=True,
    )
    db.add(business)
    db.flush()
    for agreement in data["agreements"]:
        db.add(UniversityBusinessAgreement(
            university_id=agreement["university_id"], business_id=business.id, status=AgreementStatus.APPROVED,
            allowed_bands=agreement["allowed_bands"], allowed_categories=agreement["allowed_categories"],
            requires_university_project_review=False,
            reviewed_by_admin_id=admin_by_university[agreement["university_id"]].id,
        ))
    return business


def _create_project(db: Session, data: dict, business_id: str) -> Project:
    project = Project(
        business_id=business_id, title=data["title"], description=data["description"], category=data["category"],
        required_skills=data["required_skills"], duration_label=data["duration_label"],
        estimated_hours=data["estimated_hours"], hourly_rate_gbp=data["hourly_rate_gbp"], is_remote=True,
        target_university_ids=data["target_university_ids"], target_bands=data["target_bands"],
        status=ProjectStatus.OPEN,
    )
    matching.refresh_project_embedding(project)
    db.add(project)
    return project


def _hero_business_data() -> dict:
    """Northbridge Analytics — the "hero" account for a live pitch demo.
    Its own project is deliberately NOT pre-seeded: the whole point of the
    demo is posting one live (see Task 11's browser verification and the
    printed suggested brief below) and watching real, differentiated
    matches come back."""
    return {
        "email": "demo.business@example.com",
        "full_name": "Northbridge Analytics Hiring Team",
        "company_name": "Northbridge Analytics",
        "industry": "Data & Analytics Consultancy",
        "company_registration_number": "10293847",
    }


def _hero_students_data(manchester_id: str) -> list[dict]:
    """Three hand-crafted Manchester students engineered to produce a
    clear best-to-weakest match story once "Build a customer analytics
    dashboard" (see the printed suggested brief) is posted against them —
    on top of whichever generically-generated Manchester students also
    end up on the same shortlist."""
    return [
        {  # ~90%+: exact skill overlap, strong degree match, real track record
            "email": "priya.anand@manchester.ac.uk", "full_name": "Priya Anand", "university_id": manchester_id,
            "degree_title": "BSc Data Science", "band": StudentBand.YEAR_3,
            "modules": ["Machine Learning", "Databases", "Statistics II"],
            "skills": ["Python", "SQL", "React", "Data Visualisation"],
            "hourly_rate_expectation_gbp": 20.0, "weekly_hours_available": 15,
            "is_id_verified": True, "average_rating": 4.8, "completed_projects_count": 3, "on_time_rate": 1.0,
        },
        {  # ~75-85%: strong degree match, partial skill overlap
            "email": "tom.whitfield@manchester.ac.uk", "full_name": "Tom Whitfield", "university_id": manchester_id,
            "degree_title": "BSc Computer Science", "band": StudentBand.YEAR_4_PLUS,
            "modules": ["Algorithms", "Web Development"],
            "skills": ["Python", "JavaScript", "SQL"],
            "hourly_rate_expectation_gbp": 21.0, "weekly_hours_available": 10,
            "is_id_verified": True, "average_rating": 4.5, "completed_projects_count": 1, "on_time_rate": 1.0,
        },
        {  # ~40-60%: no degree relevance, no direct skill overlap — the weak tail
            "email": "ella.marsh@manchester.ac.uk", "full_name": "Ella Marsh", "university_id": manchester_id,
            "degree_title": "BA Marketing", "band": StudentBand.YEAR_3,
            "modules": ["Digital Marketing", "Consumer Behaviour"],
            "skills": ["SEO", "Content Writing", "Excel"],
            "hourly_rate_expectation_gbp": 18.0, "weekly_hours_available": 12,
            "is_id_verified": False, "average_rating": 4.2, "completed_projects_count": 2, "on_time_rate": 0.95,
        },
    ]


def run(db: Optional[Session] = None) -> SeedSummary:
    owns_session = db is None
    if owns_session:
        Base.metadata.drop_all(engine)
        # Base.metadata.drop_all only drops ORM-registered tables —
        # alembic_version isn't one of them, so it survives the drop. If a
        # prior run already stamped this database at head,
        # run_migrations() would then see alembic_version present and,
        # believing the schema is already current, run a no-op "upgrade
        # head" instead of actually recreating the tables just dropped —
        # leaving a database with no tables but a fully-stamped
        # alembic_version, and every query below failing with "no such
        # table". Drop it too so run_migrations() correctly detects a
        # genuinely fresh database and replays a real upgrade.
        with engine.begin() as conn:
            conn.execute(text("DROP TABLE IF EXISTS alembic_version"))
        run_migrations(engine)
        db = SessionLocal()

    rng = random.Random(synthetic_data.RNG_SEED)
    used_emails: set[str] = set()

    universities = _create_universities(db)
    admin_by_university = {u.id: _create_admin(db, u) for u in universities}
    db.flush()
    manchester = next(u for u in universities if u.slug == "manchester")

    student_data = synthetic_data.generate_students(rng, universities, count=77, used_emails=used_emails)
    hero_students = _hero_students_data(manchester.id)
    used_emails.update(d["email"] for d in hero_students)  # reserve these before any business emails are generated
    student_data += hero_students
    for data in student_data:
        _create_student(db, data)

    business_data = synthetic_data.generate_businesses(rng, universities, used_emails=used_emails)
    hero_data = _hero_business_data()
    used_emails.add(hero_data["email"])
    business_data.append({**hero_data, "category": "data_analytics", "agreements": [{
        "university_id": manchester.id,
        "allowed_bands": [StudentBand.YEAR_3.value, StudentBand.YEAR_4_PLUS.value, StudentBand.POSTGRAD_TAUGHT.value],
        "allowed_categories": [ProjectCategory.DATA_ANALYTICS.value, ProjectCategory.SOFTWARE_ENGINEERING.value],
    }]})
    db.flush()
    businesses = [_create_business(db, data, admin_by_university) for data in business_data]
    db.flush()

    business_id_by_index = {i: b.id for i, b in enumerate(businesses)}
    # generate_projects only ever sees the generated (non-hero) businesses —
    # slice them off before generating so indices line up, then skip the
    # hero's own index (it posts its project live, not via this script).
    generated_businesses = business_data[:-1]
    project_data = synthetic_data.generate_projects(rng, generated_businesses, target_count=25)
    for data in project_data:
        _create_project(db, data, business_id_by_index[data["business_index"]])

    db.commit()
    summary = SeedSummary(
        universities=len(universities), students=len(student_data), businesses=len(businesses),
        projects=len(project_data), hero_business_email=hero_data["email"], hero_business_password=DEMO_PASSWORD,
    )
    if owns_session:
        db.close()
    return summary


if __name__ == "__main__":
    result = run()
    print(f"Seed complete: {result.universities} universities, {result.students} students, "
          f"{result.businesses} businesses, {result.projects} projects.")
    print(f"Hero business login: {result.hero_business_email} / {result.hero_business_password}")
    print("Suggested demo project brief for the hero account (post this live during a pitch):")
    print("  Title: Build a customer analytics dashboard")
    print("  Description: We need an interactive dashboard that visualises customer engagement, "
          "retention and revenue trends from our subscription data, so our team can make faster, "
          "data-informed decisions without waiting on manual reports.")
    print("  Category: data_analytics | Required skills: Python, SQL, Data Visualisation, React")
    print("  Duration: 2-3 weeks | Estimated hours: 20 | Rate: £22/hr")
    print("  Target: University of Manchester | Bands: year_3, year_4_plus, postgrad_taught")
