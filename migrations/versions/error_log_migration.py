
"""add_error_log_table

Revision ID: error_log_001
Revises: f6765e4cf063
Create Date: 2024-01-18 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers
revision = 'error_log_001'
down_revision = 'f6765e4cf063'
branch_labels = None
depends_on = None

def upgrade():
    op.create_table('error_log',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('timestamp', sa.DateTime(), nullable=False),
        sa.Column('error_type', sa.String(length=100), nullable=False),
        sa.Column('error_message', sa.Text(), nullable=False),
        sa.Column('stack_trace', sa.Text(), nullable=True),
        sa.Column('module', sa.String(length=100), nullable=True),
        sa.Column('endpoint', sa.String(length=200), nullable=True),
        sa.Column('user_id', sa.Integer(), nullable=True),
        sa.Column('severity', sa.String(length=20), nullable=True),
        sa.Column('status', sa.String(length=20), nullable=True),
        sa.Column('resolution_notes', sa.Text(), nullable=True),
        sa.Column('resolved_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['user.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id')
    )

def downgrade():
    op.drop_table('error_log')
