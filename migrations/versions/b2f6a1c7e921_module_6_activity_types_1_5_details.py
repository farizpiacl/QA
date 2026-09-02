"""Module 6: detail tables for Activity Types 1-5 (ramp inspection, spot checks, audit, occurrence, training)

Revision ID: b2f6a1c7e921
Revises: 9b0c90d96054
Create Date: 2026-08-28 06:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'b2f6a1c7e921'
down_revision = '9b0c90d96054'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'ramp_inspection_details',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('activity_id', sa.Integer(), nullable=False),
        sa.Column(
            'option',
            sa.Enum(
                'AS_PER_ANNUAL_PLAN', 'EU_SAFA_BOUND_FLIGHT',
                'VERIFICATION_OF_PREVIOUS_FINDINGS', 'PCAA_RAMP_INSPECTION',
                name='ramp_inspection_option',
            ),
            nullable=False,
        ),
        sa.Column('airline_id', sa.Integer(), nullable=False),
        sa.Column('aircraft_id', sa.Integer(), nullable=False),
        sa.Column('flight_number', sa.String(length=20), nullable=False),
        sa.Column('email_done', sa.Boolean(), nullable=False),
        sa.Column('qa_db_update_done', sa.Boolean(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['activity_id'], ['activities.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['airline_id'], ['airlines.id'], ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['aircraft_id'], ['aircraft.id'], ondelete='RESTRICT'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('activity_id'),
    )
    with op.batch_alter_table('ramp_inspection_details', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_ramp_inspection_details_airline_id'), ['airline_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_ramp_inspection_details_aircraft_id'), ['aircraft_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_ramp_inspection_details_activity_id'), ['activity_id'], unique=True)

    op.create_table(
        'spot_check_details',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('activity_id', sa.Integer(), nullable=False),
        sa.Column(
            'spot_check_type',
            sa.Enum(
                'AREAS', 'PREPARATION_FOLLOWUP', 'VERIFICATION', 'REPLY', 'CLOSING', 'PCAA',
                name='spot_check_type',
            ),
            nullable=False,
        ),
        sa.Column(
            'area',
            sa.Enum(
                'AIRCRAFT_SPOT_CHECKS', 'AIRCRAFT_UNSCHEDULED_RANDOM', 'ATR_MAINTENANCE',
                'A320_MAINTENANCE', 'B777_MAINTENANCE', 'PRODUCTION_DCE', 'PRODUCTION_PLANNING',
                'TOOL_STORE', 'GROUND_EQUIPMENT', 'CARDEX', 'TECHNICAL_LIBRARY',
                'TECHNICAL_STORE', 'MISCELLANEOUS',
                name='spot_check_area',
            ),
            nullable=True,
        ),
        sa.Column('airline_id', sa.Integer(), nullable=True),
        sa.Column('aircraft_id', sa.Integer(), nullable=True),
        sa.Column('flight_number', sa.String(length=20), nullable=True),
        sa.Column('email_done', sa.Boolean(), nullable=False),
        sa.Column('qa_db_update_done', sa.Boolean(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['activity_id'], ['activities.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['airline_id'], ['airlines.id'], ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['aircraft_id'], ['aircraft.id'], ondelete='RESTRICT'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('activity_id'),
    )
    with op.batch_alter_table('spot_check_details', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_spot_check_details_airline_id'), ['airline_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_spot_check_details_aircraft_id'), ['aircraft_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_spot_check_details_activity_id'), ['activity_id'], unique=True)

    op.create_table(
        'audit_details',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('activity_id', sa.Integer(), nullable=False),
        sa.Column(
            'audit_type',
            sa.Enum(
                'SCHEDULED', 'UNSCHEDULED', 'SPECIAL_PURPOSE_AUDIT', 'VERIFICATION_AUDIT',
                'DESKTOP_AUDIT', 'PRODUCT_AUDIT',
                name='audit_type',
            ),
            nullable=False,
        ),
        sa.Column(
            'section',
            sa.Enum(
                'AUDIT_OF_QA', 'LINE_MAINTENANCE', 'AWM_TSE', 'FAISALABAD_LM', 'SIALKOT_LM',
                'MULTAN_LM', 'BAHAWALPUR_LM', 'PCAA', 'EXTERNAL',
                name='audit_section',
            ),
            nullable=False,
        ),
        sa.Column('authority', sa.String(length=150), nullable=True),
        sa.Column('operator', sa.String(length=150), nullable=True),
        sa.Column('prep_status', sa.Enum('OPEN', 'CLOSED', name='audit_prep_status'), nullable=False),
        sa.Column('prep_remarks', sa.Text(), nullable=True),
        sa.Column('post_status', sa.Enum('OPEN', 'CLOSED', name='audit_post_status'), nullable=False),
        sa.Column('post_remarks', sa.Text(), nullable=True),
        sa.Column('closure_status', sa.Enum('OPEN', 'CLOSED', name='audit_closure_status'), nullable=False),
        sa.Column('closure_remarks', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['activity_id'], ['activities.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('activity_id'),
    )
    with op.batch_alter_table('audit_details', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_audit_details_activity_id'), ['activity_id'], unique=True)

    op.create_table(
        'occurrence_details',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('activity_id', sa.Integer(), nullable=False),
        sa.Column(
            'report_type',
            sa.Enum('INTERNAL', 'PCAA', 'THIRD_PARTY', name='occurrence_report_type'),
            nullable=False,
        ),
        sa.Column(
            'category',
            sa.Enum('FOD', 'BIRD_HIT', 'OTHER', name='occurrence_category'),
            nullable=False,
        ),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['activity_id'], ['activities.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('activity_id'),
    )
    with op.batch_alter_table('occurrence_details', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_occurrence_details_activity_id'), ['activity_id'], unique=True)

    op.create_table(
        'training_details',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('activity_id', sa.Integer(), nullable=False),
        sa.Column('mode', sa.Enum('CONDUCT', 'ATTEND', name='training_mode'), nullable=False),
        sa.Column(
            'kind',
            sa.Enum('CONTINUATION_TRAINING', 'RECURRENT_TRAINING', 'TYPES', name='training_kind'),
            nullable=False,
        ),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['activity_id'], ['activities.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('activity_id'),
    )
    with op.batch_alter_table('training_details', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_training_details_activity_id'), ['activity_id'], unique=True)


def downgrade():
    op.drop_table('training_details')
    op.drop_table('occurrence_details')
    op.drop_table('audit_details')
    op.drop_table('spot_check_details')
    op.drop_table('ramp_inspection_details')
