"""Audit: replace 3 separate stage sections (prep/post/closure) with a single Audit Stage dropdown

Revision ID: f6a7b8c9d215
Revises: e5f6a7b8c214
Create Date: 2026-08-31 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'f6a7b8c9d215'
down_revision = 'e5f6a7b8c214'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('audit_details', schema=None) as batch_op:
        batch_op.add_column(sa.Column(
            'audit_stage',
            sa.Enum('AUDIT_PREPARATION', 'POST_AUDIT_ACTIVITY', 'CLOSURE_OF_AUDIT', name='audit_stage'),
            nullable=False,
            server_default='AUDIT_PREPARATION',
        ))
        batch_op.add_column(sa.Column(
            'stage_status',
            sa.Enum('OPEN', 'CLOSED', name='audit_stage_status'),
            nullable=False,
            server_default='OPEN',
        ))
        batch_op.add_column(sa.Column('stage_remarks', sa.Text(), nullable=True))

    # Best-effort carry-forward: collapse the 3 old stage pairs into the new
    # single stage - prefer the first still-OPEN stage (in prep -> post ->
    # closure order), falling back to closure if all 3 were already closed,
    # so existing rows land somewhere sensible rather than losing remarks.
    conn = op.get_bind()
    conn.execute(sa.text("""
        UPDATE audit_details
        SET
            audit_stage = CASE
                WHEN prep_status = 'OPEN' THEN 'AUDIT_PREPARATION'
                WHEN post_status = 'OPEN' THEN 'POST_AUDIT_ACTIVITY'
                ELSE 'CLOSURE_OF_AUDIT'
            END,
            stage_status = CASE
                WHEN prep_status = 'OPEN' THEN prep_status
                WHEN post_status = 'OPEN' THEN post_status
                ELSE closure_status
            END,
            stage_remarks = CASE
                WHEN prep_status = 'OPEN' THEN prep_remarks
                WHEN post_status = 'OPEN' THEN post_remarks
                ELSE closure_remarks
            END
    """))

    with op.batch_alter_table('audit_details', schema=None) as batch_op:
        batch_op.alter_column('audit_stage', server_default=None)
        batch_op.alter_column('stage_status', server_default=None)
        batch_op.drop_column('prep_status')
        batch_op.drop_column('prep_remarks')
        batch_op.drop_column('post_status')
        batch_op.drop_column('post_remarks')
        batch_op.drop_column('closure_status')
        batch_op.drop_column('closure_remarks')


def downgrade():
    with op.batch_alter_table('audit_details', schema=None) as batch_op:
        batch_op.add_column(sa.Column(
            'prep_status', sa.Enum('OPEN', 'CLOSED', name='audit_prep_status'),
            nullable=False, server_default='OPEN',
        ))
        batch_op.add_column(sa.Column('prep_remarks', sa.Text(), nullable=True))
        batch_op.add_column(sa.Column(
            'post_status', sa.Enum('OPEN', 'CLOSED', name='audit_post_status'),
            nullable=False, server_default='OPEN',
        ))
        batch_op.add_column(sa.Column('post_remarks', sa.Text(), nullable=True))
        batch_op.add_column(sa.Column(
            'closure_status', sa.Enum('OPEN', 'CLOSED', name='audit_closure_status'),
            nullable=False, server_default='OPEN',
        ))
        batch_op.add_column(sa.Column('closure_remarks', sa.Text(), nullable=True))

    conn = op.get_bind()
    conn.execute(sa.text("""
        UPDATE audit_details
        SET
            prep_status = CASE WHEN audit_stage = 'AUDIT_PREPARATION' THEN stage_status ELSE 'OPEN' END,
            prep_remarks = CASE WHEN audit_stage = 'AUDIT_PREPARATION' THEN stage_remarks ELSE NULL END,
            post_status = CASE WHEN audit_stage = 'POST_AUDIT_ACTIVITY' THEN stage_status ELSE 'OPEN' END,
            post_remarks = CASE WHEN audit_stage = 'POST_AUDIT_ACTIVITY' THEN stage_remarks ELSE NULL END,
            closure_status = CASE WHEN audit_stage = 'CLOSURE_OF_AUDIT' THEN stage_status ELSE 'OPEN' END,
            closure_remarks = CASE WHEN audit_stage = 'CLOSURE_OF_AUDIT' THEN stage_remarks ELSE NULL END
    """))

    with op.batch_alter_table('audit_details', schema=None) as batch_op:
        batch_op.alter_column('prep_status', server_default=None)
        batch_op.alter_column('post_status', server_default=None)
        batch_op.alter_column('closure_status', server_default=None)
        batch_op.drop_column('audit_stage')
        batch_op.drop_column('stage_status')
        batch_op.drop_column('stage_remarks')
