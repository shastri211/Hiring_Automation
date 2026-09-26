"""drop email test override/allowlist and per-send override

Revision ID: a3d8e2f19c4b
Revises: f1a2b3c4d5e6
Create Date: 2026-09-25 10:00:00.000000

Removes the "explicitly type a different recipient" mechanisms so outbound
candidate email always goes to the address on the candidate's own resume
(CandidateProfile.email) - never a redirected or gated test address:

- app_settings.email_test_allowlist (blocked any send not explicitly
  whitelisted)
- app_settings.email_test_override_recipient (persistent, organization-wide
  redirect for automated sends)
- email_messages.override_recipient_email (per-send redirect typed into the
  Bulk Email modal)

Existing EmailMessage.status values of "BLOCKED" (produced only by the
removed allowlist gate) are left as historical records - the status column
itself is untouched, so old rows keep displaying correctly. No new message
will ever be blocked.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a3d8e2f19c4b'
down_revision: Union[str, Sequence[str], None] = 'f1a2b3c4d5e6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.drop_column('app_settings', 'email_test_allowlist')
    op.drop_column('app_settings', 'email_test_override_recipient')
    op.drop_column('email_messages', 'override_recipient_email')


def downgrade() -> None:
    """Downgrade schema."""
    op.add_column('email_messages', sa.Column('override_recipient_email', sa.String(length=255), nullable=True))
    op.add_column('app_settings', sa.Column('email_test_override_recipient', sa.String(length=255), nullable=True))
    op.add_column('app_settings', sa.Column('email_test_allowlist', sa.Text(), nullable=True))
