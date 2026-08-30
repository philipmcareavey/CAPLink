from logging.config import fileConfig

from sqlalchemy import engine_from_config
from sqlalchemy import pool

from alembic import context

# Import every model (registers them on Base.metadata) and read the same
# Settings the app itself uses, so migrations always target whatever
# DATABASE_URL the current ENVIRONMENT resolves to — never a second,
# separately-maintained connection string.
import app.models  # noqa: E402,F401 — ensures all models register with Base.metadata
from app.core.config import settings  # noqa: E402
from app.db.base_class import Base  # noqa: E402

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config
config.set_main_option("sqlalchemy.url", settings.DATABASE_URL)

# Interpret the config file for Python logging.
# This line sets up loggers basically.
#
# disable_existing_loggers=False is not optional here: the default (True)
# silently disables every already-created logger not explicitly listed in
# alembic.ini's [loggers] section — including the app's own "caplink.*"
# loggers and uvicorn's, all created before this runs since migrations are
# triggered from app/db/migrations.py during FastAPI startup, not a
# standalone `alembic` CLI invocation. A disabled logger drops every
# message with no error at all, which is exactly as silent and hard to
# debug as it sounds — this was caught by actually checking the log output
# after wiring up structured logging (Technical Implementation Plan step
# 1.c.i), not by inspection.
if config.config_file_name is not None:
    fileConfig(config.config_file_name, disable_existing_loggers=False)

target_metadata = Base.metadata

# other values from the config, defined by the needs of env.py,
# can be acquired:
# my_important_option = config.get_main_option("my_important_option")
# ... etc.


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.

    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode.

    In this scenario we need to create an Engine
    and associate a connection with the context.

    """
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection, target_metadata=target_metadata
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
