"""link_resumes_and_screening_results_to_candidate_application

Phase 1 (schema foundation) - part C of 3: additive, non-breaking columns
only. resumes.job_id/batch_id and screening_results.job_id/resume_id (plus
its existing uq_screening_job_resume constraint) are intentionally left in
place - existing ingestion/screening code keeps working unmodified. Both
new columns are nullable and non-unique here; they are populated by
scripts/backfill_candidates_applications.py for existing rows, and are only
tightened (NOT NULL / unique) at the later cutover once application code
writes them directly.

Revision ID: cb07343150ec
Revises: 588b759e7977
Create Date: 2026-09-15 14:47:52.942284

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'cb07343150ec'
down_revision: Union[str, Sequence[str], None] = '588b759e7977'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('resumes', sa.Column('candidate_id', sa.Integer(), nullable=True))
    op.create_index(op.f('ix_resumes_candidate_id'), 'resumes', ['candidate_id'], unique=False)
    op.create_foreign_key(
        'fk_resumes_candidate_id_candidates', 'resumes', 'candidates', ['candidate_id'], ['id']
    )

    op.add_column('screening_results', sa.Column('application_id', sa.Integer(), nullable=True))
    op.create_index(op.f('ix_screening_results_application_id'), 'screening_results', ['application_id'], unique=False)
    op.create_foreign_key(
        'fk_screening_results_application_id_applications', 'screening_results', 'applications', ['application_id'], ['id']
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint('fk_screening_results_application_id_applications', 'screening_results', type_='foreignkey')
    op.drop_index(op.f('ix_screening_results_application_id'), table_name='screening_results')
    op.drop_column('screening_results', 'application_id')

    op.drop_constraint('fk_resumes_candidate_id_candidates', 'resumes', type_='foreignkey')
    op.drop_index(op.f('ix_resumes_candidate_id'), table_name='resumes')
    op.drop_column('resumes', 'candidate_id')
