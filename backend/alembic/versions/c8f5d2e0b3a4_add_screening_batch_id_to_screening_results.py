"""Link screening results to the screening run that produced them

Revision ID: c8f5d2e0b3a4
Revises: b7e4c1d9a2f3
Create Date: 2026-09-26 10:05:00.000000

Lets GET /jobs/{id}/progress report each screening run's own decision
counts instead of repeating the whole job's totals on every run.

Existing rows are backfilled best-effort: each result is attributed to the
latest SCREEN batch of its job created at or before the result. Results
with no earlier SCREEN batch (e.g. an HR decision on an unscreened
candidate) stay NULL, as do all HR-created results going forward.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'c8f5d2e0b3a4'
down_revision: Union[str, Sequence[str], None] = 'b7e4c1d9a2f3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('screening_results', sa.Column('screening_batch_id', sa.Integer(), nullable=True))
    op.create_foreign_key(
        'fk_screening_results_screening_batch_id',
        'screening_results', 'screening_batches',
        ['screening_batch_id'], ['id'],
    )
    op.create_index(
        op.f('ix_screening_results_screening_batch_id'),
        'screening_results', ['screening_batch_id'], unique=False,
    )
    op.execute(
        """
        UPDATE screening_results sr
        SET screening_batch_id = (
            SELECT b.id FROM screening_batches b
            WHERE b.job_id = sr.job_id
              AND b.batch_type = 'SCREEN'
              AND b.created_at <= sr.created_at
            ORDER BY b.created_at DESC, b.id DESC
            LIMIT 1
        )
        WHERE sr.screening_batch_id IS NULL
        """
    )


def downgrade() -> None:
    op.drop_index(op.f('ix_screening_results_screening_batch_id'), table_name='screening_results')
    op.drop_constraint('fk_screening_results_screening_batch_id', 'screening_results', type_='foreignkey')
    op.drop_column('screening_results', 'screening_batch_id')
