"""add semantic score

Revision ID: 697538c321c8
Revises: 4dff423b5cbf
Create Date: 2026-09-03 16:09:18.499841

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '697538c321c8'
down_revision: Union[str, Sequence[str], None] = '4dff423b5cbf'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "screening_results",
        sa.Column("semantic_score", sa.Float(), nullable=True),
    )
    # ### end Alembic commands ###


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("screening_results", "semantic_score")
    # ### end Alembic commands ###
