"""add notification opt-outs to users

Revision ID: eb329ac42d79
Revises: b1564351e1f3
Create Date: 2026-09-18 15:10:13.616117

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'eb329ac42d79'
down_revision: Union[str, None] = 'b1564351e1f3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # server_default added by hand — autogenerate leaves it off, which is
    # fine for a brand-new table but would crash this exact migration
    # against any database that already has rows (real staging/production
    # Postgres): ADD COLUMN ... NOT NULL with no default has nothing to
    # backfill existing rows with. Same shape as mfa_backup_codes in
    # alembic/versions/c5563aee8f62_auth_hardening_lockout_email_.py.
    #
    # Autogenerate also emitted a spurious op.alter_column('milestones',
    # 'status', ...) here — a known SQLite-only false positive (SQLite has
    # no native enum type, so it represents MilestoneStatus as a plain
    # VARCHAR and diffs it against the "real" Enum every time this command
    # runs against local SQLite, even though the enum's members haven't
    # actually changed since eede1a0f59da/c9fc3db88d6f). Removed by hand,
    # same as those two prior migrations did.
    op.add_column('users', sa.Column('notification_opt_outs', sa.JSON(), nullable=False, server_default='[]'))


def downgrade() -> None:
    op.drop_column('users', 'notification_opt_outs')
