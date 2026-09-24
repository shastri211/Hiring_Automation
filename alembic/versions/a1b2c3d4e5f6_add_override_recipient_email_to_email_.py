"""add_override_recipient_email_to_email_messages

Lets a send be redirected to a tester-supplied address instead of the
candidate's real (often fake/sample-resume) email, without touching the
existing Settings > Outreach Automation allowlist mechanism - that
allowlist gates emails to *real* candidate addresses, whereas this is an
explicit, per-send override the person clicking Send typed in themselves,
so it bypasses the allowlist check entirely at send time.

Revision ID: a1b2c3d4e5f6
Revises: 09a353615425
Create Date: 2026-09-16 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, Sequence[str], None] = '09a353615425'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        'email_messages',
        sa.Column('override_recipient_email', sa.String(length=255), nullable=True),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('email_messages', 'override_recipient_email')
