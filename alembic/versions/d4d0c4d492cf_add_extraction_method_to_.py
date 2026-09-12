"""Add extraction_method to CandidateProfile

Revision ID: d4d0c4d492cf
Revises: b9092c02e5fc
Create Date: 2026-09-10 09:09:57.898164

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd4d0c4d492cf'
down_revision: Union[str, Sequence[str], None] = 'b9092c02e5fc'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('candidate_profiles', sa.Column('extraction_method', sa.String(length=50), nullable=True))
    op.add_column('candidate_profiles', sa.Column('canonical_text', sa.String(), nullable=True))
    
    # Backfill extraction_method for existing rows to LLM_ENRICHED
    op.execute("UPDATE candidate_profiles SET extraction_method = 'LLM_ENRICHED'")

def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('candidate_profiles', 'canonical_text')
    op.drop_column('candidate_profiles', 'extraction_method')
