"""Add subscription status field

Revision ID: 5a92dda42cc9
Revises: a73ab0d542eb
Create Date: 2025-01-02 02:03:00.996836

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '5a92dda42cc9'
down_revision = 'a73ab0d542eb'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('user', schema=None) as batch_op:
        batch_op.drop_column('mfa_secret')
        batch_op.drop_column('reset_token_expires')
        batch_op.drop_column('mfa_enabled')
        batch_op.drop_column('reset_token')

    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('user', schema=None) as batch_op:
        batch_op.add_column(sa.Column('reset_token', sa.VARCHAR(length=100), autoincrement=False, nullable=True))
        batch_op.add_column(sa.Column('mfa_enabled', sa.BOOLEAN(), autoincrement=False, nullable=True))
        batch_op.add_column(sa.Column('reset_token_expires', postgresql.TIMESTAMP(), autoincrement=False, nullable=True))
        batch_op.add_column(sa.Column('mfa_secret', sa.VARCHAR(length=32), autoincrement=False, nullable=True))

    # ### end Alembic commands ###
