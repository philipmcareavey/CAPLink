"""Technical Implementation Plan 1.c.iv — latency dashboards for key
endpoints. No real APM/dashboarding tool exists for this project yet (see
this step's own tracker notes), but that doesn't mean nothing usable can be
built: the structured `duration_ms` field 1.c.i's RequestLoggingMiddleware
already emits into every request's log line is exactly what a future real
APM tool would compute this same number from — this module computes it
itself, in-process, and app/api/v1/endpoints/observability.py serves it as
a real dashboard endpoint today.

Deliberately not pretending to be Datadog/Grafana: an in-memory, bounded
ring buffer per (method, route template) is per-process and resets on
restart/deploy, and doesn't aggregate across multiple Render instances if
this ever scales beyond one. That's a real, honest limitation — but this
project runs on exactly one free-tier instance today (1.d.ii, autoscaling,
is deliberately deferred), so it's a genuinely usable dashboard for the
system as it actually exists right now, not a placeholder pretending to be
more than it is.
"""
import threading
from collections import defaultdict, deque

_WINDOW_SIZE = 500
_lock = threading.Lock()
_durations_ms: dict[str, deque] = defaultdict(lambda: deque(maxlen=_WINDOW_SIZE))

# The plan's own wording (1.c.iv) calls these out by name as the most
# compute-intensive endpoints worth watching specifically.
HIGHLIGHTED_ENDPOINTS = {
    "GET /projects/feed",
    "GET /projects/{project_id}/shortlist",
    "GET /projects/{project_id}/shortlist/{student_id}/explanation",
}


def record_duration(endpoint_key: str, duration_ms: float) -> None:
    with _lock:
        _durations_ms[endpoint_key].append(duration_ms)


def _percentile(sorted_values: list, pct: float) -> float:
    if not sorted_values:
        return 0.0
    index = min(len(sorted_values) - 1, int(len(sorted_values) * pct))
    return sorted_values[index]


def snapshot() -> dict[str, dict]:
    """A point-in-time read of every endpoint's recorded latency window —
    count/avg/p50/p95/p99, in milliseconds."""
    with _lock:
        samples_by_key = {key: list(values) for key, values in _durations_ms.items() if values}

    result = {}
    for key, samples in samples_by_key.items():
        ordered = sorted(samples)
        result[key] = {
            "count": len(ordered),
            "avg_ms": round(sum(ordered) / len(ordered), 2),
            "p50_ms": round(_percentile(ordered, 0.50), 2),
            "p95_ms": round(_percentile(ordered, 0.95), 2),
            "p99_ms": round(_percentile(ordered, 0.99), 2),
        }
    return result


def reset() -> None:
    """Test-only — clears every recorded sample so tests don't leak state
    into each other via this module-level store."""
    with _lock:
        _durations_ms.clear()
