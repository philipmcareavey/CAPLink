"""
Global request body size cap (Technical Implementation Plan step 2.c.ii —
"oversized-payload risks"). Starlette/FastAPI have no built-in limit on
request body size, so without this a client can send an arbitrarily large
body and have it fully buffered/parsed before any Pydantic validation (or a
per-field max_length) ever gets a chance to reject it.

A raw ASGI middleware, not `BaseHTTPMiddleware` — deliberately. Starlette's
`BaseHTTPMiddleware` wraps the request in a `_CachedRequest` whose docstring
is explicit about a real gotcha this avoids: calling `Request.stream()`
inside `dispatch()` (the natural way to inspect a body chunk-by-chunk before
the route handler sees it) causes `_CachedRequest` to hand every
*downstream* middleware/route an EMPTY body instead of the real one — a
genuinely first-attempt-looked-fine-but-was-actually-broken trap here,
caught only by actually exercising it via TestClient rather than by
inspection (same lesson CLAUDE.md already records once for this codebase,
re: Alembic's logging side effect). Wrapping `receive` directly at the ASGI
level sidesteps that class entirely.

Checks `Content-Length` first (cheap, no body read) and rejects outright if
declared oversized; also enforces the cap while actually streaming the body,
since a client can lie about (or omit) `Content-Length`. The streaming case
works by raising _BodyTooLarge from inside `receive()` — this reaches the
route handler as it tries to read the body, before it's produced any
response, so we can still safely intercept `send` here and reply 413
ourselves (a raw ASGI app must never call `send` after it's already started
a response, so this only works because nothing downstream has sent
anything yet at that point).
"""
from starlette.types import ASGIApp, Message, Receive, Scope, Send


class _BodyTooLarge(Exception):
    pass


class MaxBodySizeMiddleware:
    def __init__(self, app: ASGIApp, max_bytes: int):
        self.app = app
        self.max_bytes = max_bytes

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        headers = dict(scope.get("headers") or [])
        content_length = headers.get(b"content-length")
        if content_length is not None:
            try:
                if int(content_length) > self.max_bytes:
                    await self._reject(send)
                    return
            except ValueError:
                pass  # malformed header — let normal request handling reject it

        seen_bytes = 0

        async def limited_receive() -> Message:
            nonlocal seen_bytes
            message = await receive()
            if message["type"] == "http.request":
                seen_bytes += len(message.get("body", b""))
                if seen_bytes > self.max_bytes:
                    raise _BodyTooLarge()
            return message

        try:
            await self.app(scope, limited_receive, send)
        except _BodyTooLarge:
            await self._reject(send)

    async def _reject(self, send: Send) -> None:
        await send(
            {
                "type": "http.response.start",
                "status": 413,
                "headers": [(b"content-type", b"application/json")],
            }
        )
        await send({"type": "http.response.body", "body": b'{"detail":"Request body too large"}'})
