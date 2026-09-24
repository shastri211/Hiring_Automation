"""add_partial_unique_index_on_active_candidate_email

Phase 2 (candidate resolution): closes a concurrency gap Phase 1 left open
deliberately for the one-time, non-concurrent backfill. Live resolution now
runs inside the worker (WORKER_CONCURRENCY=5), so two resumes sharing a new
email processed in parallel could otherwise both see "no existing
candidate" and each create one. A partial unique index - active (non
merged-away) candidates only - closes that race; app/services/
candidate_identity.py inserts under a SAVEPOINT and falls back to the
row it lost the race to on IntegrityError, mirroring the existing
file_hash-race pattern in app/api/resumes.py.

Revision ID: 09a353615425
Revises: cb07343150ec
Create Date: 2026-09-15 15:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '09a353615425'
down_revision: Union[str, Sequence[str], None] = 'cb07343150ec'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_index(
        'uq_candidates_primary_email_active',
        'candidates',
        ['primary_email'],
        unique=True,
        postgresql_where=sa.text('merged_into_id IS NULL'),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index('uq_candidates_primary_email_active', table_name='candidates')
