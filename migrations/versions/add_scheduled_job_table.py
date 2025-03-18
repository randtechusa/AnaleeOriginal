"""Add scheduled job table

Revision ID: c486451321ea
Revises: b486451321ea
Create Date: 2025-03-18 22:30:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.exc import OperationalError


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
        sa.Column('enabled', sa.Boolean(), nullable=True),
        sa.Column('last_run', sa.DateTime(), nullable=True),
        sa.Column('last_status', sa.String(length=20), nullable=True),
        sa.Column('last_error', sa.Text(), nullable=True),
        sa.Column('success_count', sa.Integer(), nullable=True),
        sa.Column('error_count', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('job_id')
    )
    
    # Add columns to audit_findings table with error handling
    try:
        # Check if details column already exists
        try:
            op.add_column('audit_findings', sa.Column('details', sa.Text(), nullable=True))
        except OperationalError as e:
            if "duplicate column name" not in str(e).lower():
                raise
        
        # Check if timestamp column already exists
        try:
            op.add_column('audit_findings', sa.Column('timestamp', sa.DateTime(), nullable=True))
        except OperationalError as e:
            if "duplicate column name" not in str(e).lower():
                raise
    except OperationalError as e:
        if "no such table" in str(e).lower():
            # If the audit_findings table doesn't exist, create it
            op.create_table('audit_findings',
                sa.Column('id', sa.Integer(), nullable=False),
                sa.Column('audit_id', sa.Integer(), nullable=False),
                sa.Column('category', sa.String(length=100), nullable=False),
                sa.Column('severity', sa.String(length=50), nullable=False),
                sa.Column('title', sa.String(length=200), nullable=False),
                sa.Column('description', sa.Text(), nullable=False),
                sa.Column('recommendation', sa.Text(), nullable=True),
                sa.Column('status', sa.String(length=50), nullable=False),
                sa.Column('resolved_at', sa.DateTime(), nullable=True),
                sa.Column('resolution_notes', sa.Text(), nullable=True),
                sa.Column('details', sa.Text(), nullable=True),
                sa.Column('timestamp', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=True),
                sa.ForeignKeyConstraint(['audit_id'], ['system_audits.id'], ),
                sa.PrimaryKeyConstraint('id')
            )
        else:
            raise


def downgrade():
    # Drop the scheduled_jobs table
    op.drop_table('scheduled_jobs')
    
    # Try to remove the added columns from audit_findings table
    try:
        op.drop_column('audit_findings', 'details')
        op.drop_column('audit_findings', 'timestamp')
    except OperationalError:
        # Ignore errors if table doesn't exist or columns already removed
        pass