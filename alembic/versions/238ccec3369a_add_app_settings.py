"""add_app_settings

Revision ID: 238ccec3369a
Revises: 66e0b88e02ab
Create Date: 2026-09-12 11:35:15.304126

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '238ccec3369a'
down_revision: Union[str, Sequence[str], None] = '66e0b88e02ab'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('app_settings',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('org_name', sa.String(length=255), nullable=True),
    sa.Column('min_candidates_to_screen', sa.Integer(), nullable=True),
    sa.Column('max_candidates_to_screen', sa.Integer(), nullable=True),
    sa.Column('semantic_gap_threshold', sa.Float(), nullable=True),
    sa.Column('auto_email_on_shortlist', sa.Boolean(), server_default=sa.text('false'), nullable=False),
    sa.Column('shortlist_email_template_id', sa.Integer(), nullable=True),
    sa.Column('auto_email_on_interview_scheduled', sa.Boolean(), server_default=sa.text('false'), nullable=False),
    sa.Column('interview_scheduled_email_template_id', sa.Integer(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
    sa.ForeignKeyConstraint(['interview_scheduled_email_template_id'], ['email_templates.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['shortlist_email_template_id'], ['email_templates.id'], ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id')
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table('app_settings')
