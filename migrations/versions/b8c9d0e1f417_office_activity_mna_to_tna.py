"""Office Activity: rename option MNA to TNA

Revision ID: b8c9d0e1f417
Revises: a7b8c9d0e316
Create Date: 2026-08-31 00:10:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'b8c9d0e1f417'
down_revision = 'a7b8c9d0e316'
branch_labels = None
depends_on = None

OLD_ENUM = sa.Enum(
    'MNA', 'MHP', 'HRT', 'IT', 'WORKS', 'OTHERS', 'MISCELLANEOUS',
    name='office_activity_option',
)
NEW_ENUM = sa.Enum(
    'TNA', 'MHP', 'HRT', 'IT', 'WORKS', 'OTHERS', 'MISCELLANEOUS',
    name='office_activity_option',
)


def upgrade():
    conn = op.get_bind()
    dialect = conn.dialect.name

    if dialect == 'postgresql':
        op.execute("ALTER TYPE office_activity_option RENAME VALUE 'MNA' TO 'TNA'")
    else:
        conn.execute(sa.text(
            "UPDATE office_activity_details SET option = 'TNA' WHERE option = 'MNA'"
        ))
        with op.batch_alter_table('office_activity_details', schema=None) as batch_op:
            batch_op.alter_column(
                'option',
                existing_type=OLD_ENUM,
                type_=NEW_ENUM,
            )


def downgrade():
    conn = op.get_bind()
    dialect = conn.dialect.name

    if dialect == 'postgresql':
        op.execute("ALTER TYPE office_activity_option RENAME VALUE 'TNA' TO 'MNA'")
    else:
        conn.execute(sa.text(
            "UPDATE office_activity_details SET option = 'MNA' WHERE option = 'TNA'"
        ))
        with op.batch_alter_table('office_activity_details', schema=None) as batch_op:
            batch_op.alter_column(
                'option',
                existing_type=NEW_ENUM,
                type_=OLD_ENUM,
            )
