"""cleanup_expired_tokens

Revision ID: 654321cba987
Revises: 1234567890ab
Create Date: 2025-10-19 19:21:00.000000

"""
from alembic import op
import sqlalchemy as sa
from datetime import datetime

# revision identifiers, used by Alembic.
revision = '654321cba987'
down_revision = '1234567890ab'
branch_labels = None
depends_on = None

def upgrade():
    # Clean up any expired tokens
    users = sa.table('users',
        sa.column('verification_token', sa.String),
        sa.column('token_expires_at', sa.DateTime),
        sa.column('reset_token', sa.String),
        sa.column('reset_token_expires', sa.DateTime)
    )
    
    # Null out expired verification tokens
    op.execute(
        users.update()
        .where(sa.and_(
            users.c.token_expires_at.isnot(None),
            users.c.token_expires_at < datetime.utcnow()
        ))
        .values(verification_token=None, token_expires_at=None)
    )
    
    # Null out expired reset tokens
    op.execute(
        users.update()
        .where(sa.and_(
            users.c.reset_token_expires.isnot(None),
            users.c.reset_token_expires < datetime.utcnow()
        ))
        .values(reset_token=None, reset_token_expires=None)
    )

def downgrade():
    # No way to restore deleted tokens
    pass
