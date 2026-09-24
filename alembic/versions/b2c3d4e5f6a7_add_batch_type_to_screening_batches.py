"""add_batch_type_to_screening_batches

Distinguishes an upload batch (Resume rows point at it via batch_id) from a
"screen job" trigger batch (never has any Resume rows pointing at it - see
app/services/screening_trigger.py - so its total_resumes is assigned
directly and is never a live resume count). Without this column, the
overview/progress endpoints had no reliable way to tell "a screen-job batch
with 0 resumes by design" apart from "an upload batch that's had every one
of its resumes deleted since" - both look identical (zero Resume rows
referencing the batch_id) - so a deleted upload batch's stale total_resumes
snapshot kept showing candidates that no longer exist.

Backfills every existing row as 'UPLOAD' (the default), then hand-corrects
the three rows in this database actually known to be screen-job batches
(472, 496, 932 - each always had total_resumes=0 with zero resumes ever
linked, the signature of a screen trigger where nothing was READY yet,
confirmed against screening_batches/resumes history). Batch 933 (job 989)
is deliberately left as UPLOAD - it was a real 15-resume upload batch later
emptied by direct DB cleanup - its total should now come from a live
resume count (0), not the stale snapshot (15).

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-09-16 13:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'b2c3d4e5f6a7'
down_revision: Union[str, Sequence[str], None] = 'a1b2c3d4e5f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_KNOWN_SCREEN_BATCH_IDS = (472, 496, 932)


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        'screening_batches',
        sa.Column('batch_type', sa.String(length=20), nullable=False, server_default='UPLOAD'),
    )
    batches = sa.table('screening_batches', sa.column('id', sa.Integer), sa.column('batch_type', sa.String))
    op.execute(
        batches.update()
        .where(batches.c.id.in_(_KNOWN_SCREEN_BATCH_IDS))
        .values(batch_type='SCREEN')
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('screening_batches', 'batch_type')
