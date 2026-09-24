"""add_shortlist_interview_automation_and_global_test_override

Two additions to app_settings:

- auto_generate_interview_on_shortlist: closes the last manual step in the
  shortlist -> interview link -> email chain. Previously, shortlisting a
  candidate could auto-email them (auto_email_on_shortlist) and triggering
  an interview could auto-email the link (auto_email_on_interview_scheduled
  - already wired, see app/services/interview.py calling
  outreach_service.on_interview_triggered), but nothing ever called
  trigger_interview automatically - a human had to open Interview Workspace
  and click "Create Interview Link" first. This toggle makes
  on_decision_shortlisted do that step too.

- email_test_override_recipient: a persistent, global counterpart to the
  Bulk Email modal's per-send "test recipient" field. That field only
  covers a manual bulk-send; there's no per-send moment for a fully
  automated send (shortlist/interview-scheduled), so this setting lets the
  same "redirect everything to my own inbox while testing" behavior apply
  there too - checked in process_send_email_task ahead of the allowlist.

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a7
Create Date: 2026-09-16 14:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'c3d4e5f6a7b8'
down_revision: Union[str, Sequence[str], None] = 'b2c3d4e5f6a7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        'app_settings',
        sa.Column('auto_generate_interview_on_shortlist', sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column(
        'app_settings',
        sa.Column('email_test_override_recipient', sa.String(length=255), nullable=True),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('app_settings', 'email_test_override_recipient')
    op.drop_column('app_settings', 'auto_generate_interview_on_shortlist')
