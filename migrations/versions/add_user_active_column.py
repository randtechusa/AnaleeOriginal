
"""Add is_active column to user table

Revision ID: add_user_active_column
"""
from alembic import op
import sqlalchemy as sa

def upgrade():
    # Add is_active column with default value True
    op.add_column('user', sa.Column('is_active', sa.Boolean(), nullable=False, server_default='1'))

def downgrade():
    op.drop_column('user', 'is_active')
