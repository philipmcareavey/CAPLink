from pydantic import BaseModel, ConfigDict

from app.models.enums import StudentBand


class BandOutcomeOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    band: StudentBand
    total_students: int
    applied_students: int
    hired_students: int
    completed_students: int
    earnings_gbp: float


class EmployabilityReportOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    total_students: int
    applied_students: int
    hired_students: int
    completed_students: int
    total_earnings_gbp: float
    average_student_rating: float | None
    rated_engagements: int
    band_breakdown: list[BandOutcomeOut]
