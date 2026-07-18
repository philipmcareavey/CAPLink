# Troubleshooting

Every error in this file is one we actually hit setting this project up on a
real, freshly-updated Mac — not a hypothetical. If you hit something not
listed here, check the traceback's last few lines first; FastAPI/Pydantic
errors are usually quite literal about what's missing.

---

### `zsh: command not found: python`

macOS only ships `python3`, never a plain `python` alias. Everywhere this
project's docs (including the top-level `README.md`) say `python`, run
`python3` instead — or activate the venv first (`source venv/bin/activate`),
which does create a `python` command that points at the venv's Python.

---

### `xcode-select: note: No developer tools were found...` when running `python3`

Apple's system `python3` is a stub that refuses to run until the Xcode Command
Line Tools are installed. Fix:

```bash
xcode-select --install
```

Click through the GUI installer that pops up. If instead you get **"not
currently available"** (seen on very new macOS versions before Apple's
software catalog has caught up), don't fight it — install Python directly from
[python.org](https://www.python.org/downloads/macos/) instead. It's fully
self-contained and doesn't need Xcode at all. Full steps in
[02-getting-started.md](02-getting-started.md#1-check-you-have-python-313).

---

### `TypeError: descriptor '__getitem__' requires a 'typing.Union' object but received a 'tuple'` on startup

You have **Python 3.14** installed instead of the required **3.13**. Python
3.14 reimplemented `typing.Union` in C ([cpython#140348](https://github.com/python/cpython/issues/140348)),
which breaks SQLAlchemy's declarative model scanning (`app/models/*.py`).
SQLAlchemy 2.0.51 has partial 3.14 support but not for this case, as of
mid-2026. Not fixable from this repo's side — install 3.13 specifically:

```bash
python3 --version   # confirm it's actually 3.14.x
```

Go to https://www.python.org/downloads/macos/, but **don't use the big
top button** (always the newest release) — scroll to a **"Python 3.13.x"**
heading instead and use its installer. Full steps in
[02-getting-started.md](02-getting-started.md#1-check-you-have-python-313).
Recreate your venv afterwards with the 3.13 binary (an existing `venv/`
folder stays pinned to whatever Python created it).

---

### `pip install -r requirements.txt` fails building `psycopg2-binary`

```
Error: pg_config executable not found.
pg_config is required to build psycopg2 from source.
```

This only happens if you're installing `requirements-postgres.txt` (Postgres
is opt-in, for production — local dev uses SQLite and never touches this
package). It means pip couldn't find a pre-built wheel for your Python
version and fell back to compiling from source, which needs a local Postgres
installation you almost certainly don't have or want for local dev. Fix:
install a newer patch version of the same package, which does have a
pre-built wheel:

```bash
pip install "psycopg2-binary==2.9.12"
```

---

### `AttributeError: module 'bcrypt' has no attribute '__about__'`

Full traceback ends in `passlib/handlers/bcrypt.py`, triggered by
`hash_password(...)`. `passlib` (last updated in 2020, unmaintained) reads an
internal `bcrypt.__about__.__version__` attribute to detect the installed
version — removed in `bcrypt>=4.1`. `requirements.txt` already pins
`bcrypt<4.1` to prevent this, so seeing this error means something in your
environment installed a newer `bcrypt` anyway (e.g. a stale venv from before
that pin was added, or a manual `pip install --upgrade bcrypt`). Fix: rebuild
your venv from a clean `pip install -r requirements.txt`, or downgrade
directly:

```bash
pip install "bcrypt==4.0.1"
```

---

### `sudo: a terminal is required to read the password`

If an AI assistant (or a script) tries to run a `sudo` command on your behalf
non-interactively, it'll fail this way — `sudo` refuses to prompt for a
password outside a real terminal. Run the printed command yourself directly in
your terminal instead.

---

### `python -m scripts.seed_demo_data` prints "Seed complete." then crashes with `DetachedInstanceError`

```
sqlalchemy.orm.exc.DetachedInstanceError: Instance <University at ...> is not
bound to a Session; attribute refresh operation cannot proceed
```

This was a genuine bug in `scripts/seed_demo_data.py`: it called `db.close()`
*before* printing `university.slug`. SQLAlchemy expires an object's loaded
attributes after `commit()`, so reading `.slug` after the session that loaded
it was already closed had nowhere to go fetch the value from. The seed data
itself had already been written successfully — only the summary print at the
end crashed. Fixed by moving `db.close()` to after the print statements (see
the file for the current, working version). If you're on an older copy of
this file and hit this, either update the script or just ignore the traceback
— your database is already seeded correctly, just re-run
`python -m scripts.seed_demo_data` a second time if you want the printed
summary (after first deleting `caplink.db`, since seeding twice into the same
database hits the next issue below).

---

### Re-running the seed script fails with a duplicate email / slug conflict

The seed script always creates the same fixed accounts (`aisha.rahman@...`,
`admin@...`, university slug `manchester`). Running it twice against the same
database violates the `unique=True` constraints on those columns. Fix: delete
the local SQLite file first.

```bash
rm caplink.db
python -m scripts.seed_demo_data
```

---

### Pasting a token into "Authorize" in `/docs` gives a 401 anyway

Double-check you copied only the `access_token` value itself — no surrounding
quotes, and not the whole JSON response. Also check it hasn't expired (access
tokens last 30 minutes by default — `ACCESS_TOKEN_EXPIRE_MINUTES` in `.env`);
just log in again and re-authorize with a fresh token. Full walkthrough of the
Authorize flow in [04-using-the-api-docs-ui.md](04-using-the-api-docs-ui.md).

---

### `Address already in use` when starting uvicorn

Something (often a previous `uvicorn --reload` process you thought you'd
stopped) is still listening on port 8000. Find and stop it:

```bash
lsof -ti:8000 | xargs kill -9
```

Then re-run `uvicorn app.main:app --reload`.
