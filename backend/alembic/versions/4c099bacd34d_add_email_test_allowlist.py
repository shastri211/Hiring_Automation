"""add_email_test_allowlist

Revision ID: 4c099bacd34d
Revises: 335c6458e928
Create Date: 2026-09-14 11:45:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '4c099bacd34d'
down_revision: Union[str, Sequence[str], None] = '335c6458e928'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('app_settings', sa.Column('email_test_allowlist', sa.Text(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('app_settings', 'email_test_allowlist')
