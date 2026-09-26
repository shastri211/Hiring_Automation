"""add_candidate_and_merge_matching_tables

Phase 1 (schema foundation) - part A of 3: introduces Candidate as a
first-class entity, separate from Resume/Application, plus its two support
tables:
  - candidate_merge_logs: audit trail for reversible candidate merges
    (Candidate.merged_into_id is the redirect pointer; merging never
    deletes or rewrites rows, so undo is just clearing that pointer).
  - candidate_match_suggestions: HR review queue for anything less certain
    than an exact-email match (name/phone/fuzzy signals never auto-merge).

Revision ID: 5f26aa062cbb
Revises: 04cf2ddb00b6
Create Date: 2026-09-15 14:47:52.942284

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '5f26aa062cbb'
down_revision: Union[str, Sequence[str], None] = '04cf2ddb00b6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('candidates',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('canonical_name', sa.String(length=255), nullable=True),
    sa.Column('primary_email', sa.String(length=255), nullable=True),
    sa.Column('primary_phone', sa.String(length=50), nullable=True),
    sa.Column('merged_into_id', sa.Integer(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
    sa.ForeignKeyConstraint(['merged_into_id'], ['candidates.id'], ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_candidates_id'), 'candidates', ['id'], unique=False)
    op.create_index(op.f('ix_candidates_merged_into_id'), 'candidates', ['merged_into_id'], unique=False)
    op.create_index(op.f('ix_candidates_primary_email'), 'candidates', ['primary_email'], unique=False)
    op.create_index(op.f('ix_candidates_primary_phone'), 'candidates', ['primary_phone'], unique=False)

    op.create_table('candidate_merge_logs',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('absorbed_candidate_id', sa.Integer(), nullable=False),
    sa.Column('into_candidate_id', sa.Integer(), nullable=False),
    sa.Column('merged_by', sa.Integer(), nullable=False),
    sa.Column('merged_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
    sa.Column('reverted_by', sa.Integer(), nullable=True),
    sa.Column('reverted_at', sa.DateTime(timezone=True), nullable=True),
    sa.ForeignKeyConstraint(['absorbed_candidate_id'], ['candidates.id'], ),
    sa.ForeignKeyConstraint(['into_candidate_id'], ['candidates.id'], ),
    sa.ForeignKeyConstraint(['merged_by'], ['users.id'], ),
    sa.ForeignKeyConstraint(['reverted_by'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_candidate_merge_logs_absorbed_candidate_id'), 'candidate_merge_logs', ['absorbed_candidate_id'], unique=False)
    op.create_index(op.f('ix_candidate_merge_logs_id'), 'candidate_merge_logs', ['id'], unique=False)
    op.create_index(op.f('ix_candidate_merge_logs_into_candidate_id'), 'candidate_merge_logs', ['into_candidate_id'], unique=False)

    op.create_table('candidate_match_suggestions',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('resume_id', sa.Integer(), nullable=False),
    sa.Column('candidate_a_id', sa.Integer(), nullable=False),
    sa.Column('candidate_b_id', sa.Integer(), nullable=False),
    sa.Column('confidence', sa.Float(), nullable=False),
    sa.Column('signals', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    sa.Column('status', sa.String(length=50), nullable=True),
    sa.Column('reviewed_by', sa.Integer(), nullable=True),
    sa.Column('reviewed_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
    sa.ForeignKeyConstraint(['candidate_a_id'], ['candidates.id'], ),
    sa.ForeignKeyConstraint(['candidate_b_id'], ['candidates.id'], ),
    sa.ForeignKeyConstraint(['resume_id'], ['resumes.id'], ),
    sa.ForeignKeyConstraint(['reviewed_by'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_candidate_match_suggestions_candidate_a_id'), 'candidate_match_suggestions', ['candidate_a_id'], unique=False)
    op.create_index(op.f('ix_candidate_match_suggestions_candidate_b_id'), 'candidate_match_suggestions', ['candidate_b_id'], unique=False)
    op.create_index(op.f('ix_candidate_match_suggestions_id'), 'candidate_match_suggestions', ['id'], unique=False)
    op.create_index(op.f('ix_candidate_match_suggestions_resume_id'), 'candidate_match_suggestions', ['resume_id'], unique=False)
    op.create_index(op.f('ix_candidate_match_suggestions_status'), 'candidate_match_suggestions', ['status'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_candidate_match_suggestions_status'), table_name='candidate_match_suggestions')
    op.drop_index(op.f('ix_candidate_match_suggestions_resume_id'), table_name='candidate_match_suggestions')
    op.drop_index(op.f('ix_candidate_match_suggestions_id'), table_name='candidate_match_suggestions')
    op.drop_index(op.f('ix_candidate_match_suggestions_candidate_b_id'), table_name='candidate_match_suggestions')
    op.drop_index(op.f('ix_candidate_match_suggestions_candidate_a_id'), table_name='candidate_match_suggestions')
    op.drop_table('candidate_match_suggestions')

    op.drop_index(op.f('ix_candidate_merge_logs_into_candidate_id'), table_name='candidate_merge_logs')
    op.drop_index(op.f('ix_candidate_merge_logs_id'), table_name='candidate_merge_logs')
    op.drop_index(op.f('ix_candidate_merge_logs_absorbed_candidate_id'), table_name='candidate_merge_logs')
    op.drop_table('candidate_merge_logs')

    op.drop_index(op.f('ix_candidates_primary_phone'), table_name='candidates')
    op.drop_index(op.f('ix_candidates_primary_email'), table_name='candidates')
    op.drop_index(op.f('ix_candidates_merged_into_id'), table_name='candidates')
    op.drop_index(op.f('ix_candidates_id'), table_name='candidates')
    op.drop_table('candidates')
