"""phase4_batch_counters_and_screening_unique

Revision ID: 53f961a6c783
Revises: 9496c5679653
Create Date: 2026-08-31 14:17:31.942799

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '53f961a6c783'
down_revision: Union[str, Sequence[str], None] = '9496c5679653'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Add columns as nullable first so existing rows do not violate NOT NULL
    op.add_column('screening_batches', sa.Column('total_resumes', sa.Integer(), nullable=True))
    op.add_column('screening_batches', sa.Column('processed', sa.Integer(), nullable=True))
    op.add_column('screening_batches', sa.Column('failed', sa.Integer(), nullable=True))
    op.add_column('screening_batches', sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True))
    # Backfill existing rows with 0
    op.execute("UPDATE screening_batches SET total_resumes = 0, processed = 0, failed = 0 WHERE total_resumes IS NULL")
    # Now make them NOT NULL
    op.alter_column('screening_batches', 'total_resumes', nullable=False)
    op.alter_column('screening_batches', 'processed', nullable=False)
    op.alter_column('screening_batches', 'failed', nullable=False)
    # Add FK and unique constraint
    op.create_foreign_key('fk_screening_batches_job_id', 'screening_batches', 'jobs', ['job_id'], ['id'])
    op.create_unique_constraint('uq_screening_job_resume', 'screening_results', ['job_id', 'resume_id'])


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint('uq_screening_job_resume', 'screening_results', type_='unique')
    op.drop_constraint('fk_screening_batches_job_id', 'screening_batches', type_='foreignkey')
    op.drop_column('screening_batches', 'updated_at')
    op.drop_column('screening_batches', 'failed')
    op.drop_column('screening_batches', 'processed')
    op.drop_column('screening_batches', 'total_resumes')
