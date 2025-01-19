
"""add filepath column

Revision ID: add_filepath_column
Create Date: 2025-01-19 01:30:00.000000
"""
from alembic import op
import sqlalchemy as sa

def upgrade():
    op.add_column('uploaded_file', sa.Column('filepath', sa.String(512), nullable=True))
    # Make existing rows have filepath same as filename initially
    op.execute("UPDATE uploaded_file SET filepath = filename")
    # Now make it not nullable
    op.alter_column('uploaded_file', 'filepath', nullable=False)

def downgrade():
    op.drop_column('uploaded_file', 'filepath')
