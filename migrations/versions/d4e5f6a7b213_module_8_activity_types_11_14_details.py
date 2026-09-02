"""Module 8: detail tables for Activity Types 11-14 (PCAA, surveillance, SMS, office activity)

Revision ID: d4e5f6a7b213
Revises: c7d3e2a5f108
Create Date: 2026-08-29 07:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'd4e5f6a7b213'
down_revision = 'c7d3e2a5f108'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'pcaa_details',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('activity_id', sa.Integer(), nullable=False),
        sa.Column('option', sa.Enum('AMS', 'LIAISON', name='pcaa_option'), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['activity_id'], ['activities.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('activity_id'),
    )
    with op.batch_alter_table('pcaa_details', schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f('ix_pcaa_details_activity_id'), ['activity_id'], unique=True
        )

    op.create_table(
        'surveillance_details',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('activity_id', sa.Integer(), nullable=False),
        sa.Column('option', sa.Enum('REPORTING', 'LIAISON', name='surveillance_option'), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['activity_id'], ['activities.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('activity_id'),
    )
    with op.batch_alter_table('surveillance_details', schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f('ix_surveillance_details_activity_id'), ['activity_id'], unique=True
        )

    op.create_table(
        'sms_details',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('activity_id', sa.Integer(), nullable=False),
        sa.Column('option', sa.Enum('REPORTING', 'LIAISON', name='sms_option'), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['activity_id'], ['activities.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('activity_id'),
    )
    with op.batch_alter_table('sms_details', schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f('ix_sms_details_activity_id'), ['activity_id'], unique=True
        )

    op.create_table(
        'office_activity_details',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('activity_id', sa.Integer(), nullable=False),
        sa.Column(
            'option',
            sa.Enum(
                'MNA', 'MHP', 'HRT', 'IT', 'WORKS', 'OTHERS', 'MISCELLANEOUS',
                name='office_activity_option',
            ),
            nullable=False,
        ),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['activity_id'], ['activities.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('activity_id'),
    )
    with op.batch_alter_table('office_activity_details', schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f('ix_office_activity_details_activity_id'), ['activity_id'], unique=True
        )


def downgrade():
    op.drop_table('office_activity_details')
    op.drop_table('sms_details')
    op.drop_table('surveillance_details')
    op.drop_table('pcaa_details')
