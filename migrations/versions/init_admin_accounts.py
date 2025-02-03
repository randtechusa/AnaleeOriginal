"""Initial migration for admin chart of accounts

Revision ID: f4383320bdef
Revises: 
Create Date: 2025-02-03 00:45:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'f4383320bdef'
down_revision = None
branch_labels = None
depends_on = None

def upgrade():
    # Create admin_chart_of_accounts table
    op.create_table('admin_chart_of_accounts',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('type', sa.String(length=50), nullable=False),
        sa.Column('code', sa.String(length=20), nullable=False),
        sa.Column('description', sa.String(length=200), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('code')
    )

def downgrade():
    op.drop_table('admin_chart_of_accounts')