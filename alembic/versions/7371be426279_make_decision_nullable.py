"""make_decision_nullable

Revision ID: 7371be426279
Revises: 697538c321c8
Create Date: 2026-09-05 22:15:00.411045

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '7371be426279'
down_revision: Union[str, Sequence[str], None] = '697538c321c8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.alter_column('screening_results', 'decision',
               existing_type=sa.VARCHAR(length=50),
               nullable=True)


def downgrade() -> None:
    """Downgrade schema."""
    op.alter_column('screening_results', 'decision',
               existing_type=sa.VARCHAR(length=50),
               nullable=False)
