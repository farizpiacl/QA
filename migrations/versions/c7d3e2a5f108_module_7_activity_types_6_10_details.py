"""Module 7: detail tables for Activity Types 6-10 (competence assessment, certificate authorization, AML application, maintenance experience, investigation)

Revision ID: c7d3e2a5f108
Revises: b2f6a1c7e921
Create Date: 2026-08-28 07:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'c7d3e2a5f108'
down_revision = 'b2f6a1c7e921'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'competence_assessment_details',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('activity_id', sa.Integer(), nullable=False),
        sa.Column(
            'personnel_type',
            sa.Enum('QA_PERSONNEL', 'MAINTENANCE_PERSONNEL', name='competence_personnel_type'),
            nullable=False,
        ),
        sa.Column('name', sa.String(length=150), nullable=False),
        sa.Column('pno_cno', sa.String(length=50), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['activity_id'], ['activities.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('activity_id'),
    )
    with op.batch_alter_table('competence_assessment_details', schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f('ix_competence_assessment_details_activity_id'), ['activity_id'], unique=True
        )

    op.create_table(
        'certificate_authorization_details',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('activity_id', sa.Integer(), nullable=False),
        sa.Column(
            'option',
            sa.Enum('CONDUCT_ORAL_ASSESSMENT', 'COORDINATION', name='certificate_authorization_option'),
            nullable=False,
        ),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['activity_id'], ['activities.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('activity_id'),
    )
    with op.batch_alter_table('certificate_authorization_details', schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f('ix_certificate_authorization_details_activity_id'), ['activity_id'], unique=True
        )

    op.create_table(
        'aml_application_details',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('activity_id', sa.Integer(), nullable=False),
        sa.Column('aml_type', sa.Enum('QA_EXAM', 'PCAA', name='aml_application_type'), nullable=False),
        sa.Column('screening', sa.Enum('YES', 'NO', name='aml_screening'), nullable=False),
        sa.Column('outcome', sa.Enum('OK', 'RETURN', name='aml_outcome'), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['activity_id'], ['activities.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('activity_id'),
    )
    with op.batch_alter_table('aml_application_details', schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f('ix_aml_application_details_activity_id'), ['activity_id'], unique=True
        )

    op.create_table(
        'maintenance_experience_details',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('activity_id', sa.Integer(), nullable=False),
        sa.Column(
            'option',
            sa.Enum('ASSESSMENT', 'SIGN_BY_QA_PERSONNEL', name='maintenance_experience_option'),
            nullable=False,
        ),
        sa.Column('name', sa.String(length=150), nullable=False),
        sa.Column('pno_cno', sa.String(length=50), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['activity_id'], ['activities.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('activity_id'),
    )
    with op.batch_alter_table('maintenance_experience_details', schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f('ix_maintenance_experience_details_activity_id'), ['activity_id'], unique=True
        )

    op.create_table(
        'investigation_details',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('activity_id', sa.Integer(), nullable=False),
        sa.Column(
            'investigation_type',
            sa.Enum('MOR', 'LOCAL_ISSUES', 'OTHERS', name='investigation_type'),
            nullable=False,
        ),
        sa.Column(
            'mor_aircraft_type',
            sa.Enum('ATR', 'A320', 'A359', 'B777', 'B787', 'OTHER', name='mor_aircraft_type'),
            nullable=True,
        ),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['activity_id'], ['activities.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('activity_id'),
    )
    with op.batch_alter_table('investigation_details', schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f('ix_investigation_details_activity_id'), ['activity_id'], unique=True
        )


def downgrade():
    op.drop_table('investigation_details')
    op.drop_table('maintenance_experience_details')
    op.drop_table('aml_application_details')
    op.drop_table('certificate_authorization_details')
    op.drop_table('competence_assessment_details')
