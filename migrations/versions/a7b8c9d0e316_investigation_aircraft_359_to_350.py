"""Investigation: rename MOR aircraft type A359 to A350

Revision ID: a7b8c9d0e316
Revises: f6a7b8c9d215
Create Date: 2026-08-31 00:05:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'a7b8c9d0e316'
down_revision = 'f6a7b8c9d215'
branch_labels = None
depends_on = None

OLD_ENUM = sa.Enum('ATR', 'A320', 'A359', 'B777', 'B787', 'OTHER', name='mor_aircraft_type')
NEW_ENUM = sa.Enum('ATR', 'A320', 'A350', 'B777', 'B787', 'OTHER', name='mor_aircraft_type')


def upgrade():
    conn = op.get_bind()
    dialect = conn.dialect.name

    if dialect == 'postgresql':
        op.execute("ALTER TYPE mor_aircraft_type RENAME VALUE 'A359' TO 'A350'")
    else:
        # SQLite/others: enums aren't a real DB type, just update the data and
        # let the column's Python-side Enum validate against the new choices.
        conn.execute(sa.text(
            "UPDATE investigation_details SET mor_aircraft_type = 'A350' "
            "WHERE mor_aircraft_type = 'A359'"
        ))
        with op.batch_alter_table('investigation_details', schema=None) as batch_op:
            batch_op.alter_column(
                'mor_aircraft_type',
                existing_type=OLD_ENUM,
                type_=NEW_ENUM,
            )


def downgrade():
    conn = op.get_bind()
    dialect = conn.dialect.name

    if dialect == 'postgresql':
        op.execute("ALTER TYPE mor_aircraft_type RENAME VALUE 'A350' TO 'A359'")
    else:
        conn.execute(sa.text(
            "UPDATE investigation_details SET mor_aircraft_type = 'A359' "
            "WHERE mor_aircraft_type = 'A350'"
        ))
        with op.batch_alter_table('investigation_details', schema=None) as batch_op:
            batch_op.alter_column(
                'mor_aircraft_type',
                existing_type=NEW_ENUM,
                type_=OLD_ENUM,
            )
