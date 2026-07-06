"""
Seed script — creates a demo university, an approved business agreement,
a student, a business, and a project so you can explore the API immediately.

Run with:  python -m scripts.seed_demo_data
"""
from app.core.security import hash_password
from app.db.base_class import Base
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

import app.models  # noqa: F401


def run():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()

    university = University(
        name="University of Manchester",
        slug="manchester",
        domain="manchester.ac.uk",
        primary_color="#1B2A45",
        license_tier=UniversityLicenseTier.ENTERPRISE,
        license_status=UniversityLicenseStatus.ACTIVE,
        license_seats=5000,
        primary_contact_name="Careers & Employability Service",
        primary_contact_email="careers@manchester.ac.uk",
    )
    db.add(university)
    db.flush()

    admin_user = User(
        email="admin@manchester.ac.uk",
        hashed_password=hash_password("ChangeMe123!"),
        role=UserRole.UNIVERSITY_ADMIN,
        full_name="Careers Service Admin",
        university_id=university.id,
        is_email_verified=True,
    )
    db.add(admin_user)

    student_user = User(
        email="aisha.rahman@manchester.ac.uk",
        hashed_password=hash_password("ChangeMe123!"),
        role=UserRole.STUDENT,
        full_name="Aisha Rahman",
        university_id=university.id,
        is_email_verified=True,
    )
    db.add(student_user)
    db.flush()

    student_profile = StudentProfile(
        user_id=student_user.id,
        university_id=university.id,
        degree_title="BSc Data Science",
        band=StudentBand.YEAR_3,
        modules=["Statistics II", "Machine Learning", "Databases"],
        skills=["Python", "SQL", "Data Visualisation"],
        hourly_rate_expectation_gbp=19.0,
        weekly_hours_available=10,
        is_id_verified=True,
        average_rating=4.9,
        completed_projects_count=7,
        on_time_rate=0.98,
    )
    db.add(student_profile)

    business_user = User(
        email="hello@datacraft-analytics.com",
        hashed_password=hash_password("ChangeMe123!"),
        role=UserRole.BUSINESS,
        full_name="DataCraft Analytics Hiring Team",
    )
    db.add(business_user)
    db.flush()

    business_profile = BusinessProfile(
        user_id=business_user.id,
        company_name="DataCraft Analytics",
        company_registration_number="12345678",
        industry="Data & Analytics Consultancy",
        global_trust_tier=BusinessTrustTier.UNIVERSITY_APPROVED,
        is_registration_verified=True,
    )
    db.add(business_profile)
    db.flush()

    agreement = UniversityBusinessAgreement(
        university_id=university.id,
        business_id=business_profile.id,
        status=AgreementStatus.APPROVED,
        allowed_bands=[StudentBand.YEAR_2.value, StudentBand.YEAR_3.value, StudentBand.YEAR_4_PLUS.value,
                       StudentBand.POSTGRAD_TAUGHT.value],
        allowed_categories=[ProjectCategory.DATA_ANALYTICS.value, ProjectCategory.RESEARCH.value],
        reviewed_by_admin_id=admin_user.id,
    )
    db.add(agreement)

    project = Project(
        business_id=business_profile.id,
        title="Customer Churn Analysis",
        description="Analyse 12 months of subscription data to identify the top churn drivers.",
        category=ProjectCategory.DATA_ANALYTICS,
        required_skills=["Python", "SQL", "Statistics"],
        duration_label="1-2 weeks",
        estimated_hours=15,
        hourly_rate_gbp=19.0,
        is_remote=True,
        target_university_ids=[university.id],
        target_bands=[StudentBand.YEAR_3.value, StudentBand.POSTGRAD_TAUGHT.value],
        status=ProjectStatus.OPEN,
    )
    db.add(project)

    db.commit()
    print("Seed complete.")
    print(f"University slug: {university.slug}")
    print("Student login: aisha.rahman@manchester.ac.uk / ChangeMe123!")
    print("Business login: hello@datacraft-analytics.com / ChangeMe123!")
    print("University admin login: admin@manchester.ac.uk / ChangeMe123!")
    db.close()


if __name__ == "__main__":
    run()
