"""add_user_activity_tracking

Revision ID: 1234567890ab
Revises: 
Create Date: 2025-10-19 19:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '1234567890ab'
down_revision = None
branch_labels = None
depends_on = None

def upgrade():
    # Add the new columns to the users table
    op.add_column('users', sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')))
    op.add_column('users', sa.Column('last_active', sa.DateTime(), nullable=False, server_default=sa.text('now()')))
    op.add_column('users', sa.Column('is_active', sa.Boolean(), nullable=False, server_default='t'))
    
    # Create an index on last_active for potential future use (like finding inactive accounts)
    op.create_index(op.f('ix_users_last_active'), 'users', ['last_active'], unique=False)
    
    # Update existing users to have is_active=True
    users_table = sa.table('users',
                         sa.column('is_active', sa.Boolean()),
                         sa.column('created_at', sa.DateTime()),
                         sa.column('last_active', sa.DateTime()))
    op.execute(
        users_table.update().values(
            is_active=True,
            created_at=sa.text('now()'),
            last_active=sa.text('now()')
        )
    )

def downgrade():
    # Drop the index first
    op.drop_index(op.f('ix_users_last_active'), table_name='users')
    
    # Then drop the columns
    op.drop_column('users', 'is_active')
    op.drop_column('users', 'last_active')
    op.drop_column('users', 'created_at')
