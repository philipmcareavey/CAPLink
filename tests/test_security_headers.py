from starlette.applications import Starlette
from starlette.responses import PlainTextResponse
from starlette.routing import Route
from starlette.testclient import TestClient

from app.core.security_headers import HSTSMiddleware


def _make_app():
    async def homepage(request):
        return PlainTextResponse("ok")

    app = Starlette(routes=[Route("/", homepage)])
    app.add_middleware(HSTSMiddleware)
    return app


def test_hsts_header_present_with_correct_directives():
    client = TestClient(_make_app())
    response = client.get("/")
    assert response.headers["strict-transport-security"] == "max-age=63072000; includeSubDomains"


def test_hsts_custom_max_age():
    async def homepage(request):
        return PlainTextResponse("ok")

    app = Starlette(routes=[Route("/", homepage)])
    app.add_middleware(HSTSMiddleware, max_age=3600)
    client = TestClient(app)
    response = client.get("/")
    assert response.headers["strict-transport-security"] == "max-age=3600; includeSubDomains"
