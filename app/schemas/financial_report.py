from pydantic import BaseModel, ConfigDict


class ProjectSpendOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    project_id: str
    project_title: str
    paid_gbp: float
    pending_capture_gbp: float


class BusinessSpendReportOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    total_paid_gbp: float
    total_pending_capture_gbp: float
    monthly_paid_gbp: dict[str, float]
    by_project: list[ProjectSpendOut]


class PlatformRevenueReportOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    gross_payment_volume_gbp: float
    platform_fee_revenue_gbp: float
    monthly_platform_fee_revenue_gbp: dict[str, float]
    license_revenue_gbp: float
