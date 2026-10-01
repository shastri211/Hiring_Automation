"""add organizations (multi-tenancy) + user roles/verification

Revision ID: f1a2b3c4d5e6
Revises: e7a1c2b3d4f5
Create Date: 2026-09-24 20:00:00.000000

Adds organizations and an organization_id on every root table (jobs,
candidates, users, email_templates, app_settings, talent_pool_entries).
All existing rows are backfilled into one organization; existing users
become verified admins and platform admins (they are this deployment's
operators). Per-org uniqueness replaces the old global rules for template
names, the active-candidate-email index, and the app_settings singleton.

Downgrade is only possible while a single organization exists.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f1a2b3c4d5e6'
down_revision: Union[str, Sequence[str], None] = 'e7a1c2b3d4f5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

DEFAULT_ORG_NAME = "Default Organization"

_ROOT_TABLES = ("jobs", "candidates", "users", "email_templates", "app_settings", "talent_pool_entries")


def upgrade() -> None:
    """Upgrade schema."""
    bind = op.get_bind()

    # -- pre-checks: refuse rather than silently merge/lose data -------------
    dup_emails = bind.execute(sa.text(
        "SELECT lower(trim(email)) FROM users GROUP BY 1 HAVING count(*) > 1"
    )).scalars().all()
    if dup_emails:
        raise RuntimeError(
            f"{len(dup_emails)} user email(s) collide after lower(trim()) normalization; "
            "resolve the duplicate accounts before running this migration."
        )
    settings_rows = bind.execute(sa.text("SELECT count(*) FROM app_settings")).scalar_one()
    if settings_rows > 1:
        raise RuntimeError(
            f"Expected at most 1 app_settings row (the old singleton), found {settings_rows}."
        )

    # -- organizations + the backfill target ----------------------------------
    op.create_table(
        'organizations',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_organizations_id'), 'organizations', ['id'], unique=False)

    existing_name = bind.execute(sa.text(
        "SELECT org_name FROM app_settings WHERE org_name IS NOT NULL AND trim(org_name) <> '' LIMIT 1"
    )).scalar_one_or_none()
    default_org_id = bind.execute(
        sa.text("INSERT INTO organizations (name) VALUES (:name) RETURNING id"),
        {"name": (existing_name or DEFAULT_ORG_NAME).strip()},
    ).scalar_one()

    # -- organization_id on every root table ---------------------------------
    for table in _ROOT_TABLES:
        op.add_column(table, sa.Column('organization_id', sa.Integer(), nullable=True))
        bind.execute(sa.text(f"UPDATE {table} SET organization_id = :org"), {"org": default_org_id})
        op.alter_column(table, 'organization_id', nullable=False)
        op.create_foreign_key(
            f'fk_{table}_organization_id', table, 'organizations', ['organization_id'], ['id']
        )
        op.create_index(
            op.f(f'ix_{table}_organization_id'), table, ['organization_id'],
            unique=(table == 'app_settings'),
        )

    # -- users: roles, verification, forced password change, platform admin --
    op.add_column('users', sa.Column('role', sa.String(length=20), server_default='member', nullable=False))
    op.add_column('users', sa.Column('email_verified_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('users', sa.Column('must_change_password', sa.Boolean(), server_default=sa.false(), nullable=False))
    op.add_column('users', sa.Column('is_platform_admin', sa.Boolean(), server_default=sa.false(), nullable=False))
    bind.execute(sa.text(
        "UPDATE users SET role = 'admin', email_verified_at = now(), is_platform_admin = true, "
        "email = lower(trim(email))"
    ))
    op.create_index('uq_users_email_lower', 'users', [sa.text('lower(email)')], unique=True)

    # -- per-org uniqueness ---------------------------------------------------
    op.drop_constraint('email_templates_name_key', 'email_templates', type_='unique')
    op.create_unique_constraint('uq_email_templates_org_name', 'email_templates', ['organization_id', 'name'])

    op.drop_index('uq_candidates_primary_email_active', table_name='candidates')
    op.create_index(
        'uq_candidates_primary_email_active', 'candidates', ['organization_id', 'primary_email'],
        unique=True, postgresql_where=sa.text('merged_into_id IS NULL'),
    )

    # Organization.name replaces the per-app name.
    op.drop_column('app_settings', 'org_name')


def downgrade() -> None:
    """Downgrade schema."""
    bind = op.get_bind()
    org_count = bind.execute(sa.text("SELECT count(*) FROM organizations")).scalar_one()
    if org_count > 1:
        raise RuntimeError(
            f"Refusing to downgrade: {org_count} organizations exist, and the pre-tenancy "
            "schema can't represent more than one without merging their data."
        )

    op.add_column('app_settings', sa.Column('org_name', sa.String(length=255), nullable=True))
    bind.execute(sa.text(
        "UPDATE app_settings SET org_name = o.name FROM organizations o "
        "WHERE o.id = app_settings.organization_id AND o.name <> :default"
    ), {"default": DEFAULT_ORG_NAME})

    op.drop_index('uq_candidates_primary_email_active', table_name='candidates')
    op.create_index(
        'uq_candidates_primary_email_active', 'candidates', ['primary_email'],
        unique=True, postgresql_where=sa.text('merged_into_id IS NULL'),
    )

    op.drop_constraint('uq_email_templates_org_name', 'email_templates', type_='unique')
    op.create_unique_constraint('email_templates_name_key', 'email_templates', ['name'])

    op.drop_index('uq_users_email_lower', table_name='users')
    op.drop_column('users', 'is_platform_admin')
    op.drop_column('users', 'must_change_password')
    op.drop_column('users', 'email_verified_at')
    op.drop_column('users', 'role')

    for table in reversed(_ROOT_TABLES):
        op.drop_index(op.f(f'ix_{table}_organization_id'), table_name=table)
        op.drop_constraint(f'fk_{table}_organization_id', table, type_='foreignkey')
        op.drop_column(table, 'organization_id')

    op.drop_index(op.f('ix_organizations_id'), table_name='organizations')
    op.drop_table('organizations')
