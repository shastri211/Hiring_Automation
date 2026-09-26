"""add_unique_constraint_resumes_job_file_hash

Revision ID: 04cf2ddb00b6
Revises: 4c099bacd34d
Create Date: 2026-09-14 12:31:21.943224

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '04cf2ddb00b6'
down_revision: Union[str, Sequence[str], None] = '4c099bacd34d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_unique_constraint(
        "uq_resumes_job_id_file_hash", "resumes", ["job_id", "file_hash"]
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint("uq_resumes_job_id_file_hash", "resumes", type_="unique")
