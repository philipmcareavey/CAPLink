from fastapi import APIRouter

from app.api.v1.endpoints import (
    applications,
    auth,
    businesses,
    contracts,
    messages,
    mobile,
    policies,
    projects,
    ratings,
    recommendations,
    students,
    universities,
)

api_router = APIRouter()

api_router.include_router(auth.router)
api_router.include_router(universities.router)
api_router.include_router(policies.router)
api_router.include_router(students.router)
api_router.include_router(businesses.router)
api_router.include_router(projects.router)
api_router.include_router(applications.router)
api_router.include_router(contracts.router)
api_router.include_router(ratings.router)
api_router.include_router(messages.router)
api_router.include_router(recommendations.router)
api_router.include_router(mobile.router)
