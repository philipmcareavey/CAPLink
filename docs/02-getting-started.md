# Getting Started (Mac)

This walks through getting the demo running from a clean Mac. If something
below doesn't match what you see, check
[06-troubleshooting.md](06-troubleshooting.md) — it documents every real
error hit while writing this guide, not hypothetical ones.

There are two ways to run this: **VS Code** (fewest manual steps, recommended)
or the **plain terminal**. Both end up in the same place.

## 0. Get the code

```bash
git clone git@github.com:philipmcareavey/CAPLink.git
cd CAPLink/caplink
```

(If you don't have SSH keys set up for GitHub, use the HTTPS clone URL from
the repo's green "Code" button instead.)

## 1. Check you have Python 3.13

This project **requires Python 3.13** — not 3.14. Python 3.14 reimplemented
`typing.Union` in C, which breaks SQLAlchemy's model scanning on startup with
`TypeError: descriptor '__getitem__' requires a 'typing.Union' object but
received a 'tuple'`. It's a known CPython 3.14 regression, not a bug in this
project, and not fixable from this repo's side. A `.python-version` file in
the repo root records the required version for any tooling that reads it
(e.g. `pyenv`).

```bash
python3 --version
```

- **If this prints `3.13.x`**, skip to step 2.
- **If it prints `3.14.x` or something older than 3.13**, or errors out
  mentioning **Xcode** / **command line developer tools** (macOS's built-in
  `python3` is a stub that refuses to run until Apple's Command Line Tools
  are installed), install 3.13 specifically from python.org:

  1. Go to https://www.python.org/downloads/macos/.
  2. **Don't click the big "Download Python 3.x" button at the top** — it's
     always the newest release. Scroll down for a heading that says
     **"Python 3.13.x"** specifically and use its "macOS 64-bit universal2
     installer" `.pkg` link.
  3. Double-click it and click through the installer (needs your admin
     password).
  4. Confirm it worked:
     ```bash
     /usr/local/bin/python3.13 --version
     ```

  The rest of this guide calls it `python3` — if you installed via
  python.org, substitute `/usr/local/bin/python3.13` (or whichever path the
  installer printed) wherever `python3` appears below.

## Option A — VS Code (recommended)

1. Open the `caplink/` folder in VS Code.
2. VS Code will offer to install the Python extension, then to create a
   virtual environment and install `requirements.txt` — accept both prompts.
   (No prompt? Run **Python: Create Environment** from the Command Palette —
   ⇧⌘P — and pick `requirements.txt`.)
3. Open **Run and Debug** (⇧⌘D) and run **"CAPLink: Run demo (backend +
   browser)"**. This starts the API on `localhost:8000` and automatically
   opens `http://localhost:8000/demo/app.html` in your default browser.

No `.env` file or manual seeding needed — every setting has a working local
default, and the server seeds a demo university/student/business/project on
first run automatically. Log in as the student with
`aisha.rahman@manchester.ac.uk` / `ChangeMe123!` (see
[03-user-guide-demo-walkthrough.md](03-user-guide-demo-walkthrough.md) for
the business/admin logins too). You're done — skip to
[Confirm it's running](#confirm-its-running) below.

## Option B — terminal

From inside the `caplink/` folder:

```bash
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

Once installed, sanity-check the core imports:

```bash
python -c "import fastapi, sqlalchemy, pydantic, jose, passlib, email_validator; print('OK')"
```

`.env` is **optional** — every setting in `app/core/config.py` has a sensible
local default (SQLite, permissive CORS, etc). Only copy it if you want to
override something:

```bash
cp .env.example .env
```

Then run the server:

```bash
uvicorn app.main:app --reload
```

The server auto-seeds a demo university/student/business/project on first
run (same as VS Code — this happens automatically whenever `ENVIRONMENT`
is `development`, which is the default). If you'd rather seed manually or
re-seed after wiping the database, that's still available:

```bash
python -m scripts.seed_demo_data
```

Expected seed output:

```
Seed complete.
University slug: manchester
Student login: aisha.rahman@manchester.ac.uk / ChangeMe123!
Business login: hello@datacraft-analytics.com / ChangeMe123!
University admin login: admin@manchester.ac.uk / ChangeMe123!
```

Re-running the seed script twice without deleting the database first fails
with duplicate-key errors (the demo emails/slug already exist). To start
over:

```bash
rm caplink.db
python -m scripts.seed_demo_data
```

## Confirm it's running

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

Then open one of:

- **http://localhost:8000/demo/app.html** — the live demo app (login, feed,
  applications; see [03-user-guide-demo-walkthrough.md](03-user-guide-demo-walkthrough.md))
- **http://localhost:8000/app** — the fuller build covering nearly the whole
  API for all three roles; see [deploy-locally.md](deploy-locally.md)
- **http://localhost:8000/docs** — the interactive Swagger API explorer; see
  [04-using-the-api-docs-ui.md](04-using-the-api-docs-ui.md) for a login
  quirk worth knowing about first

## Quick reference: full setup, start to finish

```bash
git clone git@github.com:philipmcareavey/CAPLink.git
cd CAPLink/caplink
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
uvicorn app.main:app --reload   # auto-seeds demo data on first run
```
