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
import logging
from pathlib import Path

from alembic.config import Config
from alembic import command
from sqlalchemy import inspect
from sqlalchemy.engine import Engine

REPO_ROOT = Path(__file__).resolve().parent.parent.parent


def run_migrations(engine: Engine) -> None:
    # alembic/env.py calls logging.config.fileConfig(alembic.ini) as a side
    # effect of loading — that resets the ROOT logger's level/handlers to
    # alembic.ini's own plain-text config ([logger_root] level=WARN), which
    # would otherwise leak out of this function and silently break the
    # app's own structured JSON logging (Technical Implementation Plan step
    # 1.c.i) every single time this runs — including the second, redundant
    # call inside scripts/seed_demo_data.py's run(). Save/restore the root
    # logger's state around the alembic call so this function never has that
    # side effect on its caller, no matter who calls it or how many times.
    root_logger = logging.getLogger()
    saved_handlers, saved_level = root_logger.handlers[:], root_logger.level

    alembic_cfg = Config(str(REPO_ROOT / "alembic.ini"))
    alembic_cfg.set_main_option("script_location", str(REPO_ROOT / "alembic"))

    existing_tables = set(inspect(engine).get_table_names())
    try:
        if existing_tables and "alembic_version" not in existing_tables:
            command.stamp(alembic_cfg, "head")
        else:
            command.upgrade(alembic_cfg, "head")
    finally:
        root_logger.handlers, root_logger.level = saved_handlers, saved_level
