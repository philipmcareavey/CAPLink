"""
Observability setup (Technical Implementation Plan steps 1.c.i–1.c.ii):
structured JSON logging for every log line the process emits, and optional
Sentry error tracking.

Both are called once from app/main.py's startup hook, after uvicorn has
already done its own logging setup — reconfiguring here, not at import time,
is what lets this override uvicorn's own plain-text formatters regardless of
how the process was actually started (`uvicorn app.main:app --reload`
locally, or the bare `uvicorn ...` command in render.yaml's startCommand).
"""
import json
import logging

# Every standard LogRecord attribute — anything else on the record came from
# a caller's `extra={...}` and should ride along as its own JSON field
# (e.g. request_id, method, path, status_code, duration_ms) rather than
# being invisible to whoever/whatever queries these logs afterward.
_STANDARD_LOG_RECORD_ATTRS = {
    "name", "msg", "args", "levelname", "levelno", "pathname", "filename",
    "module", "exc_info", "exc_text", "stack_info", "lineno", "funcName",
    "created", "msecs", "relativeCreated", "thread", "threadName",
    "processName", "process", "message", "taskName", "color_message",
}


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "timestamp": self.formatTime(record, "%Y-%m-%dT%H:%M:%S%z"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        for key, value in record.__dict__.items():
            if key not in _STANDARD_LOG_RECORD_ATTRS:
                payload[key] = value
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str)


def configure_logging(level: str) -> None:
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())

    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(level)

    # uvicorn's "uvicorn"/"uvicorn.error" loggers (startup/shutdown/error
    # messages) ship with their own plain-text handlers — replace those so
    # they come out as JSON too, consistent with everything else.
    for name in ("uvicorn", "uvicorn.error"):
        uv_logger = logging.getLogger(name)
        uv_logger.handlers = [handler]
        uv_logger.propagate = False

    # uvicorn.access is disabled outright, not just reformatted — main.py's
    # RequestLoggingMiddleware already emits one structured JSON line per
    # request with real separate fields (method/path/status_code/
    # duration_ms), so leaving this on would double-log every request.
    logging.getLogger("uvicorn.access").disabled = True


def configure_error_tracking(dsn: str, environment: str) -> None:
    """No-op if dsn is empty — see SENTRY_DSN's docstring in config.py."""
    if not dsn:
        return
    import sentry_sdk

    sentry_sdk.init(dsn=dsn, environment=environment, send_default_pii=False)
