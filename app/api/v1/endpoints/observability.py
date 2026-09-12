from fastapi import APIRouter, Depends

from app.api.deps import require_platform_admin
from app.core import latency_metrics
from app.models.user import User

router = APIRouter(prefix="/observability", tags=["observability"])


@router.get("/latency-dashboard")
def get_latency_dashboard(_admin: User = Depends(require_platform_admin)):
    """Technical Implementation Plan 1.c.iv — count/avg/p50/p95/p99
    latency (milliseconds) per endpoint, over this process's most recent
    requests. See app/core/latency_metrics.py's own docstring for exactly
    what this can and can't do (in-process, per-instance, resets on
    restart) and why that's a genuinely usable answer to this step today
    rather than a placeholder waiting on a real APM tool."""
    endpoints = latency_metrics.snapshot()
    return {
        "endpoints": endpoints,
        "highlighted_endpoints": sorted(latency_metrics.HIGHLIGHTED_ENDPOINTS & endpoints.keys()),
    }
