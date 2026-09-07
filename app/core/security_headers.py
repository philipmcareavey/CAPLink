"""
HSTS (Technical Implementation Plan 7.d.ii — "enforce TLS everywhere and
HSTS"). TLS termination itself is Render's job, not this app's — Render
terminates HTTPS at its edge automatically for every *.onrender.com
service and any custom domain, with no code-level configuration (see
README's "Data protection & privacy engineering" section). What Render
does NOT do on its own is tell a returning browser "never use plain HTTP
for this origin again, even if a link or bookmark points at it" — that's
what the Strict-Transport-Security header does, and it has to come from
the application.

Only added outside `development`: a local `http://localhost` origin
doesn't want a browser refusing to fall back to HTTP later, and HSTS is
meaningless without TLS actually terminating somewhere in front of the
app anyway (which only staging/production have, via Render).
"""
from starlette.types import ASGIApp, Message, Receive, Scope, Send


class HSTSMiddleware:
    def __init__(self, app: ASGIApp, max_age: int = 63072000):
        self.app = app
        self.header_value = f"max-age={max_age}; includeSubDomains".encode()

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        async def add_header(message: Message) -> None:
            if message["type"] == "http.response.start":
                headers = list(message.get("headers", []))
                headers.append((b"strict-transport-security", self.header_value))
                message["headers"] = headers
            await send(message)

        await self.app(scope, receive, add_header)
