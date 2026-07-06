# Using the API Docs (the "User Interface")

CAPLink doesn't have a website or app in this repository yet — it's a backend
API only. The closest thing to a "user interface" you can click around in
right now is **Swagger UI**, which FastAPI generates automatically at:

```
http://localhost:8000/docs
```

(There's also a machine-readable version at `/openapi.json`, and a
differently-styled explorer at `/redoc` — same information, different look.)

## What you'll see

Each router from `app/api/v1/endpoints/` shows up as a collapsible section
(FastAPI calls these "tags"): **auth**, **universities**, **safeguarding-policies**,
**students**, **businesses**, **projects**, **applications**, **contracts**,
**ratings**, **messages**, **recommendations**, **mobile**. Click a section to
expand its endpoints; click an endpoint to see its full request/response shape
(this is generated straight from the Pydantic schemas in `app/schemas/`, so it's
always accurate to the code).

Every endpoint has a **"Try it out"** button — click it, fill in the fields,
click **Execute**, and it makes a real HTTP request against your local server
and shows you the actual response, status code, and the equivalent `curl`
command. This works great for:

- `GET /health`
- `GET /universities/{slug}/public`
- `POST /auth/register/student`, `POST /auth/register/business`
- `POST /auth/login`

## Using the "Authorize" button

Swagger UI has a green **Authorize** padlock icon near the top of the page.
Clicking it lets you paste in a token once and have it automatically attached
to every subsequent "Try it out" call, so you don't have to re-enter auth for
every endpoint.

Under the hood, `app/api/deps.py` uses FastAPI's
[`HTTPBearer`](https://fastapi.tiangolo.com/reference/security/#fastapi.security.HTTPBearer)
security scheme, which tells Swagger UI to show a single free-text field for
pasting a raw bearer token — matching what this API actually expects
(`Authorization: Bearer <token>`), rather than trying to run its own OAuth2
login form against a login endpoint that doesn't speak that protocol.

**To authenticate in `/docs`:**

1. Expand `POST /auth/login`, click **Try it out**, fill in one of the seeded
   accounts' email/password (see
   [03-user-guide-demo-walkthrough.md](03-user-guide-demo-walkthrough.md)),
   and click **Execute**.
2. Copy the `access_token` string out of the response body (without quotes).
3. Click the **Authorize** padlock near the top of the page, paste the token
   into the **Value** field, and click **Authorize**, then **Close**.
4. Every protected endpoint's "Try it out" now sends that token automatically
   — try `GET /students/me` or `GET /projects/feed` to confirm.

Access tokens expire after 30 minutes (`ACCESS_TOKEN_EXPIRE_MINUTES` in
`.env`) — if calls start failing with 401 partway through a session, just
log in again and re-authorize with the fresh token.

> **A note on how this API used to be wired, in case you're reading older
> notes or a previous version of this file:** it originally used
> `OAuth2PasswordBearer`, which is the scheme FastAPI's own tutorials default
> to for JWT auth. That scheme tells Swagger the Authorize button should submit
> an OAuth2 "password grant" form (`grant_type`/`username`/`password` as
> `application/x-www-form-urlencoded`) straight to the login URL — but this
> API's login endpoint takes JSON (`{"email": ..., "password": ...}`), so that
> automatic form submission 422'd. `OAuth2PasswordBearer` is only doing double
> duty as "a way to read a bearer token out of the Authorization header" here,
> not backing a real OAuth2 token endpoint — a common mismatch when
> tutorial-style FastAPI JWT auth meets a custom JSON login body.
> `app/api/deps.py` now uses `HTTPBearer` instead, which doesn't make that
> assumption, so the Authorize button works as described above.
