"""Add must_change_password to users (forces password change for the
default bootstrap Super Admin account)

Revision ID: e5f6a7b8c214
Revises: d4e5f6a7b213
Create Date: 2026-08-29 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'e5f6a7b8c214'
down_revision = 'd4e5f6a7b213'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.add_column(
            sa.Column(
                'must_change_password',
                sa.Boolean(),
                nullable=False,
                server_default=sa.false(),
            )
        )
    # Drop the server_default after backfilling existing rows so future
    # inserts rely on the application-level default instead (matches the
    # pattern used for is_active on this table).
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.alter_column('must_change_password', server_default=None)


def downgrade():
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.drop_column('must_change_password')
