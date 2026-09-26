"""Track confirmed queue enqueue for recruiter-uploaded resumes

Revision ID: d9a6e3f1c4b5
Revises: c8f5d2e0b3a4
Create Date: 2026-09-26 15:00:00.000000

Bulk upload enqueued each resume after committing it; if Redis failed
mid-way, the rest stayed UPLOADED forever with nothing to recover them.
resumes.enqueued_at records a confirmed enqueue so the worker's recovery
sweep (resume_intake.requeue_unenqueued_uploads) can re-enqueue the rest.

Existing rows were all enqueued (or processed) before this column existed,
so they are backfilled with created_at - none should be swept.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'd9a6e3f1c4b5'
down_revision: Union[str, Sequence[str], None] = 'c8f5d2e0b3a4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('resumes', sa.Column('enqueued_at', sa.DateTime(timezone=True), nullable=True))
    op.execute("UPDATE resumes SET enqueued_at = created_at WHERE enqueued_at IS NULL")
    op.create_index(
        'ix_resumes_unenqueued', 'resumes', ['created_at'], unique=False,
        postgresql_where=sa.text('enqueued_at IS NULL'),
    )


def downgrade() -> None:
    op.drop_index('ix_resumes_unenqueued', table_name='resumes', postgresql_where=sa.text('enqueued_at IS NULL'))
    op.drop_column('resumes', 'enqueued_at')
