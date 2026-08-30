"""
Import every model here so both `Base.metadata` (Alembic's autogenerate,
see alembic/env.py) and the Alembic migration chain itself (app/db/migrations.py)
know about every table.
"""
from app.models.university import University          # noqa: F401
from app.models.user import User, StudentProfile, BusinessProfile  # noqa: F401
from app.models.policy import UniversityBusinessAgreement          # noqa: F401
from app.models.project import Project                # noqa: F401
from app.models.application import Application         # noqa: F401
from app.models.contract import Contract, Milestone    # noqa: F401
from app.models.rating import Rating                   # noqa: F401
from app.models.message import MessageThread, Message  # noqa: F401
from app.models.device import Device                   # noqa: F401
from app.models.recommendation import RecommendationLog  # noqa: F401
