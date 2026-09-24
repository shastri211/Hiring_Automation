"""add_application_history_and_decision_audit

Phase 1 (schema foundation) - part B of 3: introduces Application as the
first-class (candidate, job) relationship - UNIQUE(candidate_id, job_id) so
a candidate can never have two Applications to the same job. Application
only points at a *current* resume (current_resume_id); it does not use a
resume as its identity. ApplicationResumeHistory preserves every resume
that was ever current for an application, and DecisionAudit preserves every
automated/HR decision change, so nothing is lost when a resume or a
decision is superseded.

Revision ID: 588b759e7977
Revises: 5f26aa062cbb
Create Date: 2026-09-15 14:47:52.942284

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '588b759e7977'
down_revision: Union[str, Sequence[str], None] = '5f26aa062cbb'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('applications',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('candidate_id', sa.Integer(), nullable=False),
    sa.Column('job_id', sa.Integer(), nullable=False),
    sa.Column('current_resume_id', sa.Integer(), nullable=False),
    sa.Column('batch_id', sa.Integer(), nullable=False),
    sa.Column('status', sa.String(length=50), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
    sa.ForeignKeyConstraint(['batch_id'], ['screening_batches.id'], ),
    sa.ForeignKeyConstraint(['candidate_id'], ['candidates.id'], ),
    sa.ForeignKeyConstraint(['current_resume_id'], ['resumes.id'], ),
    sa.ForeignKeyConstraint(['job_id'], ['jobs.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('candidate_id', 'job_id', name='uq_applications_candidate_job')
    )
    op.create_index(op.f('ix_applications_batch_id'), 'applications', ['batch_id'], unique=False)
    op.create_index(op.f('ix_applications_candidate_id'), 'applications', ['candidate_id'], unique=False)
    op.create_index(op.f('ix_applications_current_resume_id'), 'applications', ['current_resume_id'], unique=False)
    op.create_index(op.f('ix_applications_id'), 'applications', ['id'], unique=False)
    op.create_index(op.f('ix_applications_job_id'), 'applications', ['job_id'], unique=False)

    op.create_table('application_resume_history',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('application_id', sa.Integer(), nullable=False),
    sa.Column('resume_id', sa.Integer(), nullable=False),
    sa.Column('batch_id', sa.Integer(), nullable=True),
    sa.Column('used_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
    sa.ForeignKeyConstraint(['application_id'], ['applications.id'], ),
    sa.ForeignKeyConstraint(['batch_id'], ['screening_batches.id'], ),
    sa.ForeignKeyConstraint(['resume_id'], ['resumes.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_application_resume_history_application_id'), 'application_resume_history', ['application_id'], unique=False)
    op.create_index(op.f('ix_application_resume_history_batch_id'), 'application_resume_history', ['batch_id'], unique=False)
    op.create_index(op.f('ix_application_resume_history_id'), 'application_resume_history', ['id'], unique=False)
    op.create_index(op.f('ix_application_resume_history_resume_id'), 'application_resume_history', ['resume_id'], unique=False)

    op.create_table('decision_audits',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('application_id', sa.Integer(), nullable=False),
    sa.Column('event_type', sa.String(length=50), nullable=False),
    sa.Column('actor_type', sa.String(length=20), nullable=False),
    sa.Column('actor_id', sa.Integer(), nullable=True),
    sa.Column('old_decision', sa.String(length=50), nullable=True),
    sa.Column('new_decision', sa.String(length=50), nullable=True),
    sa.Column('old_score', sa.Float(), nullable=True),
    sa.Column('new_score', sa.Float(), nullable=True),
    sa.Column('reason', sa.Text(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
    sa.ForeignKeyConstraint(['actor_id'], ['users.id'], ),
    sa.ForeignKeyConstraint(['application_id'], ['applications.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_decision_audits_application_id'), 'decision_audits', ['application_id'], unique=False)
    op.create_index(op.f('ix_decision_audits_event_type'), 'decision_audits', ['event_type'], unique=False)
    op.create_index(op.f('ix_decision_audits_id'), 'decision_audits', ['id'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_decision_audits_id'), table_name='decision_audits')
    op.drop_index(op.f('ix_decision_audits_event_type'), table_name='decision_audits')
    op.drop_index(op.f('ix_decision_audits_application_id'), table_name='decision_audits')
    op.drop_table('decision_audits')

    op.drop_index(op.f('ix_application_resume_history_resume_id'), table_name='application_resume_history')
    op.drop_index(op.f('ix_application_resume_history_id'), table_name='application_resume_history')
    op.drop_index(op.f('ix_application_resume_history_batch_id'), table_name='application_resume_history')
    op.drop_index(op.f('ix_application_resume_history_application_id'), table_name='application_resume_history')
    op.drop_table('application_resume_history')

    op.drop_index(op.f('ix_applications_job_id'), table_name='applications')
    op.drop_index(op.f('ix_applications_id'), table_name='applications')
    op.drop_index(op.f('ix_applications_current_resume_id'), table_name='applications')
    op.drop_index(op.f('ix_applications_candidate_id'), table_name='applications')
    op.drop_index(op.f('ix_applications_batch_id'), table_name='applications')
    op.drop_table('applications')
