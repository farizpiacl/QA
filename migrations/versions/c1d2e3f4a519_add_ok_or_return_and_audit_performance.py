"""Add Maintenance Experience Action field and 'Audit Performance' audit stage

Revision ID: c1d2e3f4a519
Revises: b8c9d0e1f417
Create Date: 2026-09-02 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'c1d2e3f4a519'
down_revision = 'b8c9d0e1f417'
branch_labels = None
depends_on = None


def upgrade():
    # --- Maintenance Experience: new "Action" dropdown (OK / Return) -------
    # Existing rows have no action recorded yet; backfill them to 'OK' so the
    # column can be made NOT NULL, then drop the server default so it's no
    # longer applied to future inserts (the app always sends an explicit
    # value).
    with op.batch_alter_table('maintenance_experience_details', schema=None) as batch_op:
        batch_op.add_column(sa.Column(
            'action',
            sa.Enum('OK', 'RETURN', name='maintenance_experience_action'),
            nullable=False,
            server_default='OK',
        ))

    with op.batch_alter_table('maintenance_experience_details', schema=None) as batch_op:
        batch_op.alter_column('action', server_default=None)

    # --- Audit: new "Audit Performance" audit stage option -----------------
    # Postgres requires ALTER TYPE ... ADD VALUE to run outside a transaction
    # block, so it's issued in its own autocommit block.
    with op.get_context().autocommit_block():
        op.execute("ALTER TYPE audit_stage ADD VALUE IF NOT EXISTS 'AUDIT_PERFORMANCE'")


def downgrade():
    with op.batch_alter_table('maintenance_experience_details', schema=None) as batch_op:
        batch_op.drop_column('action')

    # Postgres does not support removing a value from an enum type directly.
    # Downgrading the audit_stage addition would require recreating the enum
    # type (and remapping any rows using the new value), which is
    # intentionally not automated here to avoid silent data loss. If a
    # downgrade is needed, handle manually:
    #   1. Reassign/clear rows using 'AUDIT_PERFORMANCE'
    #   2. Recreate the audit_stage enum type without the added value
    #   3. Swap the column over to the recreated type
    raise NotImplementedError(
        "Partial downgrade only: the 'action' column was dropped, but "
        "Postgres cannot drop the 'AUDIT_PERFORMANCE' enum value in place. "
        "See migration docstring for the manual recreation steps."
    )
