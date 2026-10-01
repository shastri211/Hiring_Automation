"""Make jobs.status NOT NULL with an ACTIVE default

Revision ID: b7e4c1d9a2f3
Revises: a3d8e2f19c4b
Create Date: 2026-09-26 10:00:00.000000

10c7626cca95 added jobs.status as nullable with no server default, so jobs
created before it (or inserted outside the ORM) have NULL status. The
pipeline only processes ACTIVE jobs and pause/resume only act on
ACTIVE/PAUSED, so a NULL-status job's resumes were stuck in UPLOADED with no
way to recover them from the UI. Those jobs predate the status column and
were always treated as live, so they are backfilled as ACTIVE.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'b7e4c1d9a2f3'
down_revision: Union[str, Sequence[str], None] = 'a3d8e2f19c4b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("UPDATE jobs SET status = 'ACTIVE' WHERE status IS NULL")
    op.alter_column(
        'jobs', 'status',
        existing_type=sa.String(length=50),
        nullable=False,
        server_default='ACTIVE',
    )


def downgrade() -> None:
    op.alter_column(
        'jobs', 'status',
        existing_type=sa.String(length=50),
        nullable=True,
        server_default=None,
    )
