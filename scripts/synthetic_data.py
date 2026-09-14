"""
Deterministic synthetic-data vocabulary and small helpers, used by
scripts/seed_demo_data.py (Workstream 9.a) to build a realistic-feeling
demo dataset. Deterministic (a fixed RNG seed) so reseeding produces the
same dataset every time — no drift between demo runs.
"""
import random

RNG_SEED = 20260913

FIRST_NAMES = [
    "Aisha", "Elif", "Femi", "Rosa", "Jack", "Sofia", "Liam", "Mia",
    "Omar", "Grace", "Noah", "Zara", "Ben", "Freya", "Ali", "Ruby",
    "Sam", "Isla", "Leo", "Amara", "Finn", "Nadia", "Josh", "Erin",
]

LAST_NAMES = [
    "Rahman", "Vasquez", "Okafor", "Lindqvist", "Doyle", "Petrova", "Nguyen",
    "Osei", "Fitzgerald", "Yamamoto", "Kaur", "Byrne", "Larsson", "Haddad",
    "Okoye", "Sullivan", "Ibrahim", "Novak", "Reilly", "Adeyemi", "Kowalski",
    "Blackwood", "Hassan", "Fenwick",
]

# NOTE: "Priya"/"Anand", "Tom"/"Whitfield", and "Ella"/"Marsh" are
# deliberately absent from the pools above — those three exact names are
# reserved for the hand-crafted hero-scenario students in
# scripts/seed_demo_data.py's _hero_students_data(), and must never be
# producible by the random generator (a coincidental duplicate would still
# get a de-duplicated email via unique_email(), but would confusingly
# imply two different people with the same name).

# (degree_title, primary ProjectCategory value) — degree titles are written
# to literally contain a "strong" keyword from
# app/services/matching/config.py's CATEGORY_KEYWORDS, so generated
# students score realistically against app/services/matching/degree.py.
DEGREE_POOL = [
    ("BSc Computer Science", "software_engineering"),
    ("BSc Data Science", "data_analytics"),
    ("BSc Software Engineering", "software_engineering"),
    ("MSc Data Analytics", "data_analytics"),
    ("BSc Statistics", "data_analytics"),
    ("BA Marketing", "marketing"),
    ("BA Communications", "marketing"),
    ("BA Media Studies", "marketing"),
    ("BA Graphic Design", "design"),
    ("BA Art", "design"),
    ("BSc Media Production", "design"),
    ("BSc Economics", "finance"),
    ("BSc Accounting and Finance", "finance"),
    ("BSc Business Management", "operations"),
    ("BSc Mathematics", "data_analytics"),
    ("BSc Environmental Science", "research"),
]

SKILLS_BY_CATEGORY = {
    "software_engineering": ["Python", "JavaScript", "React", "Node.js", "SQL", "Git", "Java", "TypeScript"],
    "data_analytics": ["Python", "SQL", "Statistics", "Machine Learning", "Data Visualisation", "Excel", "R", "Power BI"],
    "marketing": ["SEO", "Content Writing", "Social Media", "Google Analytics", "Email Marketing", "Copywriting"],
    "design": ["Figma", "Adobe Creative Suite", "UI", "UX", "Illustration", "Branding", "Prototyping"],
    "finance": ["Excel", "Financial Modelling", "Accounting", "Statistics"],
    "operations": ["Project Management", "Excel", "Process Improvement", "Stakeholder Management"],
    "research": ["Statistics", "R", "Data Visualisation", "Excel"],
}

# 18 hand-authored businesses, spread across categories so
# university-business agreements and generated projects have real variety.
# "Northbridge Analytics" is deliberately NOT in this list — that name is
# reserved for the hand-crafted hero account in seed_demo_data.py, which
# is a 19th, separate business (total businesses in the seeded dataset is
# 18 + 1 hero = 19, not 18).
BUSINESS_TEMPLATES = [
    {"company_name": "Riverstone Data Partners", "industry": "Data & Analytics Consultancy", "category": "data_analytics"},
    {"company_name": "Cascade Insights", "industry": "Market Research", "category": "data_analytics"},
    {"company_name": "Ledger & Loop", "industry": "Fintech Analytics", "category": "data_analytics"},
    {"company_name": "Foundry Software", "industry": "Software Development", "category": "software_engineering"},
    {"company_name": "Brightwell Digital", "industry": "Web & App Development", "category": "software_engineering"},
    {"company_name": "Kestrel Systems", "industry": "Enterprise Software", "category": "software_engineering"},
    {"company_name": "Marlow & Finch", "industry": "Marketing Agency", "category": "marketing"},
    {"company_name": "Loudmouth Media", "industry": "Social Media Marketing", "category": "marketing"},
    {"company_name": "Hearth Brand Studio", "industry": "Brand Strategy", "category": "marketing"},
    {"company_name": "Fernhollow Studio", "industry": "Design Agency", "category": "design"},
    {"company_name": "Paperclip Creative", "industry": "Graphic Design", "category": "design"},
    {"company_name": "Willowmere Design Co.", "industry": "Product Design", "category": "design"},
    {"company_name": "Amberly Finance Partners", "industry": "Financial Services", "category": "finance"},
    {"company_name": "Northstone Accounting", "industry": "Accounting", "category": "finance"},
    {"company_name": "Greybridge Logistics", "industry": "Logistics & Operations", "category": "operations"},
    {"company_name": "Hollowfield Ops", "industry": "Operations Consultancy", "category": "operations"},
    {"company_name": "Bramwell Environmental", "industry": "Environmental Consultancy", "category": "research"},
    {"company_name": "Sable Research Collective", "industry": "Independent Research", "category": "research"},
]

PROJECT_TEMPLATES_BY_CATEGORY = {
    "data_analytics": [
        {"title": "Customer Churn Analysis", "description": "Analyse subscription data to identify the top drivers of customer churn.", "required_skills": ["Python", "SQL", "Statistics"], "duration_label": "1-2 weeks", "estimated_hours": 15, "hourly_rate_gbp": 19},
        {"title": "Sales Dashboard Build", "description": "Build an interactive dashboard visualising regional sales trends for the leadership team.", "required_skills": ["SQL", "Data Visualisation", "Excel"], "duration_label": "2-3 weeks", "estimated_hours": 20, "hourly_rate_gbp": 20},
    ],
    "software_engineering": [
        {"title": "Internal Tools Prototype", "description": "Build a small internal web tool to replace a manual spreadsheet workflow.", "required_skills": ["Python", "JavaScript", "SQL"], "duration_label": "2-3 weeks", "estimated_hours": 18, "hourly_rate_gbp": 21},
        {"title": "API Integration", "description": "Integrate a third-party payments API into our existing backend service.", "required_skills": ["Python", "Git"], "duration_label": "1-2 weeks", "estimated_hours": 14, "hourly_rate_gbp": 22},
    ],
    "marketing": [
        {"title": "SEO Content Audit", "description": "Audit our existing site content and propose an SEO improvement plan.", "required_skills": ["SEO", "Content Writing"], "duration_label": "1 week", "estimated_hours": 10, "hourly_rate_gbp": 17},
        {"title": "Social Campaign Plan", "description": "Plan and schedule a month-long social media campaign for a product launch.", "required_skills": ["Social Media", "Copywriting"], "duration_label": "1-2 weeks", "estimated_hours": 12, "hourly_rate_gbp": 17},
    ],
    "design": [
        {"title": "Brand Refresh", "description": "Refresh our logo and brand guidelines for a more modern look.", "required_skills": ["Figma", "Branding"], "duration_label": "2 weeks", "estimated_hours": 16, "hourly_rate_gbp": 18},
        {"title": "App UI Redesign", "description": "Redesign our mobile app's onboarding flow for clarity and accessibility.", "required_skills": ["Figma", "UI", "UX"], "duration_label": "2-3 weeks", "estimated_hours": 18, "hourly_rate_gbp": 19},
    ],
    "finance": [
        {"title": "Budget Model Build", "description": "Build a rolling 12-month budget model in a spreadsheet for our finance team.", "required_skills": ["Excel", "Financial Modelling"], "duration_label": "1-2 weeks", "estimated_hours": 14, "hourly_rate_gbp": 19},
    ],
    "operations": [
        {"title": "Process Mapping", "description": "Map and document our order-fulfilment process to find efficiency gains.", "required_skills": ["Process Improvement", "Excel"], "duration_label": "1-2 weeks", "estimated_hours": 12, "hourly_rate_gbp": 17},
    ],
    "research": [
        {"title": "Literature Review", "description": "Conduct a literature review on sustainable packaging alternatives.", "required_skills": ["Statistics", "Data Visualisation"], "duration_label": "1-2 weeks", "estimated_hours": 12, "hourly_rate_gbp": 17},
    ],
}


def unique_email(rng: "random.Random | None", first: str, last: str, domain: str, used: set[str]) -> str:
    """Builds first.last@domain, appending a numeric suffix on collision.
    `rng` is accepted for interface consistency with the other generator
    functions but isn't actually needed here — collisions are resolved
    deterministically by counting up, not by rerolling."""
    base = f"{first.lower()}.{last.lower()}@{domain}"
    if base not in used:
        used.add(base)
        return base
    n = 2
    while f"{first.lower()}.{last.lower()}{n}@{domain}" in used:
        n += 1
    email = f"{first.lower()}.{last.lower()}{n}@{domain}"
    used.add(email)
    return email
