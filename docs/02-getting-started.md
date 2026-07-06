# Getting Started

This walks through getting the demo running from a completely clean Mac. If
something below doesn't match what you see, check
[06-troubleshooting.md](06-troubleshooting.md) — it documents every real error hit
while writing this guide, not hypothetical ones.

## 1. Check you have a working Python 3

```bash
python3 --version
```

If this prints a version (3.10+), skip to step 2.

If instead you get an error mentioning **Xcode** or **command line developer
tools**, macOS's built-in `python3` is a stub that refuses to run until Apple's
Command Line Tools are installed. Normally:

```bash
xcode-select --install
```

...pops up a small installer — click through it and wait a few minutes, then
re-run `python3 --version`.

**If that installer fails with "not currently available"** (this can happen on a
very new macOS version before Apple's catalog has caught up), skip Xcode entirely
and install Python directly from python.org instead — it's self-contained and
doesn't need Xcode:

1. Go to https://www.python.org/downloads/macos/ and download the latest
   "macOS 64-bit universal2 installer" `.pkg`.
2. Double-click it and click through the installer (needs your admin password).
3. Confirm it worked:
   ```bash
   /usr/local/bin/python3 --version
   ```

Either way, you now have a working `python3`. The rest of this guide calls it
`python3` — if you used the python.org installer, that's `/usr/local/bin/python3`.

## 2. Create a virtual environment and install dependencies

From inside the `caplink/` folder:

```bash
cd caplink
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

**Two packages in `requirements.txt` are likely to need a small override on a
new Python version, because their pinned versions predate that Python release
getting pre-built binary wheels:**

- **`psycopg2-binary==2.9.9`** — if `pip install` fails trying to *compile* it
  (an error mentioning `pg_config` / "Getting requirements to build wheel...
  error"), install a newer patch version instead — it's the same package, just
  built for your Python version:
  ```bash
  pip install "psycopg2-binary==2.9.12"
  ```
  (This is only used for a *production* Postgres database — local dev uses
  SQLite and never touches this package.)

- **`passlib[bcrypt]==1.7.4`** pulls in whatever the latest `bcrypt` is, but
  `passlib` 1.7.4 (unmaintained since 2020) reads an internal `bcrypt.__about__`
  attribute that was removed in `bcrypt>=4.1`. If you see
  `AttributeError: module 'bcrypt' has no attribute '__about__'`, pin an older
  bcrypt:
  ```bash
  pip install "bcrypt==4.0.1"
  ```

- **`email-validator`** isn't in `requirements.txt` at all, but Pydantic's
  `EmailStr` type (used for every email field) needs it at import time. If the
  server fails to start with `email-validator is not installed`, add it:
  ```bash
  pip install "pydantic[email]==2.9.2"
  ```

Once installed, sanity-check everything imports:

```bash
python -c "import fastapi, sqlalchemy, pydantic, jose, passlib, psycopg2, stripe, firebase_admin, email_validator; print('OK')"
```

## 3. Configure environment variables

```bash
cp .env.example .env
```

SQLite works out of the box — you don't need to edit anything to run the demo
locally. (`.env` points `DATABASE_URL` at a local `caplink.db` file. Swap it for
a `postgresql://...` URL only when you actually have a Postgres server running.)

## 4. Seed demo data

This creates one working "tenant" end-to-end: a licensed university, an approved
business, a student, and an open project, so you have something to look at
immediately instead of an empty database.

```bash
python -m scripts.seed_demo_data
```

Expected output:

```
Seed complete.
University slug: manchester
Student login: aisha.rahman@manchester.ac.uk / ChangeMe123!
Business login: hello@datacraft-analytics.com / ChangeMe123!
University admin login: admin@manchester.ac.uk / ChangeMe123!
```

Re-running this script twice without deleting the database first will fail with
duplicate-key errors (the demo emails/slug already exist). To start over:

```bash
rm caplink.db
python -m scripts.seed_demo_data
```

## 5. Run the server

```bash
uvicorn app.main:app --reload
```

You should see something like:

```
INFO:     Uvicorn running on http://127.0.0.1:8000 (Press CTRL+C to quit)
INFO:     Application startup complete.
```

Confirm it's alive:

```bash
curl http://localhost:8000/health
# {"status":"ok","app":"CAPLink","environment":"development"}
```

Then open **http://localhost:8000/docs** in a browser — this is the interactive
API explorer. See [04-using-the-api-docs-ui.md](04-using-the-api-docs-ui.md) for
how to actually use it (there's a login quirk worth knowing about first), and
[03-user-guide-demo-walkthrough.md](03-user-guide-demo-walkthrough.md) for a full
worked demo.

## Quick reference: full setup, start to finish

```bash
cd caplink
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
# if needed: pip install "psycopg2-binary==2.9.12" "bcrypt==4.0.1" "pydantic[email]==2.9.2"
cp .env.example .env
python -m scripts.seed_demo_data
uvicorn app.main:app --reload
```
