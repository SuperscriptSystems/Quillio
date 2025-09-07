"""add password reset fields

Revision ID: 1a2b3c4d5e6f
Revises: d4e8f1a9b3c7
Create Date: 2025-09-06 17:45:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '1a2b3c4d5e6f'
down_revision = 'd4e8f1a9b3c7'
branch_labels = None
depends_on = None

def upgrade():
    # Add reset_token column
    op.add_column('users', sa.Column('reset_token', sa.String(length=100), nullable=True))
    # Add reset_token_expires column
    op.add_column('users', sa.Column('reset_token_expires', sa.DateTime(), nullable=True))
    # Create index for reset_token
    op.create_index(op.f('ix_users_reset_token'), 'users', ['reset_token'], unique=True)

def downgrade():
    # Drop the index first
    op.drop_index(op.f('ix_users_reset_token'), table_name='users')
    # Drop the columns
    op.drop_column('users', 'reset_token_expires')
    op.drop_column('users', 'reset_token')
