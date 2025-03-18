"""Add scheduled job table

Revision ID: c486451321ea
Revises: b486451321ea
Create Date: 2025-03-18 22:30:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'c486451321ea'
down_revision = 'b486451321ea'
branch_labels = None
depends_on = None


def upgrade():
    # Create the scheduled_jobs table
    op.create_table('scheduled_jobs',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('job_id', sa.String(length=100), nullable=False),
        sa.Column('description', sa.String(length=200), nullable=True),
        sa.Column('enabled', sa.Boolean(), nullable=True, default=True),
        sa.Column('last_run', sa.DateTime(), nullable=True),
        sa.Column('last_status', sa.String(length=20), nullable=True),
        sa.Column('last_error', sa.Text(), nullable=True),
        sa.Column('success_count', sa.Integer(), nullable=True, default=0),
        sa.Column('error_count', sa.Integer(), nullable=True, default=0),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('job_id')
    )
    
    # Add details column to audit_findings table
    op.add_column('audit_findings', sa.Column('details', sa.Text(), nullable=True))
    
    # Add timestamp column to audit_findings table if not present
    op.add_column('audit_findings', sa.Column('timestamp', sa.DateTime(), nullable=True))


def downgrade():
    # Drop the scheduled_jobs table
    op.drop_table('scheduled_jobs')
    
    # Remove the added columns from audit_findings
    op.drop_column('audit_findings', 'details')
    op.drop_column('audit_findings', 'timestamp')