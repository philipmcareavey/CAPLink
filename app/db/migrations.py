"""
Runs the Alembic migration chain against `engine` at process startup —
replaces the old `Base.metadata.create_all(bind=engine)` call (Technical
Implementation Plan step 1.a.iii).

Databases created before Alembic existed (this Mac's local `caplink.db`,
Render's existing staging deploy, anyone else's already-seeded dev copy)
already have every table `create_all` used to make, but no `alembic_version`
row recording that. Running a normal `upgrade` against one of those would
try to `CREATE TABLE` things that already exist and crash. So: if the
database already has tables but no `alembic_version` table, it's stamped as
already being at `head` instead of replaying the baseline migration —
otherwise it's a genuinely fresh database and gets a real `upgrade`.
"""
from pathlib import Path

from alembic.config import Config
from alembic import command
from sqlalchemy import inspect
from sqlalchemy.engine import Engine

REPO_ROOT = Path(__file__).resolve().parent.parent.parent


def run_migrations(engine: Engine) -> None:
    alembic_cfg = Config(str(REPO_ROOT / "alembic.ini"))
    alembic_cfg.set_main_option("script_location", str(REPO_ROOT / "alembic"))

    existing_tables = set(inspect(engine).get_table_names())
    if existing_tables and "alembic_version" not in existing_tables:
        command.stamp(alembic_cfg, "head")
    else:
        command.upgrade(alembic_cfg, "head")
