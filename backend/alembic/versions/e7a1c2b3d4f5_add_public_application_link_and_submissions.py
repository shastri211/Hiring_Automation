"""add public application link and submissions

Revision ID: e7a1c2b3d4f5
Revises: 8c93135170fd
Create Date: 2026-09-24 18:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e7a1c2b3d4f5'
down_revision: Union[str, Sequence[str], None] = '8c93135170fd'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('jobs', sa.Column('application_token', sa.String(length=64), nullable=True))
    op.create_index(op.f('ix_jobs_application_token'), 'jobs', ['application_token'], unique=True)

    op.create_table(
        'public_application_submissions',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('resume_id', sa.Integer(), nullable=False),
        sa.Column('job_id', sa.Integer(), nullable=False),
        sa.Column('applicant_name', sa.String(length=255), nullable=False),
        sa.Column('applicant_email', sa.String(length=320), nullable=False),
        sa.Column('applicant_phone', sa.String(length=50), nullable=True),
        sa.Column('consent_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('enqueued_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['job_id'], ['jobs.id']),
        sa.ForeignKeyConstraint(['resume_id'], ['resumes.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('resume_id'),
    )
    op.create_index(op.f('ix_public_application_submissions_id'), 'public_application_submissions', ['id'], unique=False)
    op.create_index(op.f('ix_public_application_submissions_job_id'), 'public_application_submissions', ['job_id'], unique=False)
    op.create_index(
        'ix_public_application_submissions_unenqueued',
        'public_application_submissions',
        ['created_at'],
        unique=False,
        postgresql_where=sa.text('enqueued_at IS NULL'),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index('ix_public_application_submissions_unenqueued', table_name='public_application_submissions')
    op.drop_index(op.f('ix_public_application_submissions_job_id'), table_name='public_application_submissions')
    op.drop_index(op.f('ix_public_application_submissions_id'), table_name='public_application_submissions')
    op.drop_table('public_application_submissions')
    op.drop_index(op.f('ix_jobs_application_token'), table_name='jobs')
    op.drop_column('jobs', 'application_token')
