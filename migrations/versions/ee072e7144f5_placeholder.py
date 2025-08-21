"""placeholder for existing DB head

Revision ID: ee072e7144f5
Revises: 
Create Date: 2025-08-21 19:50:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'ee072e7144f5'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    # This is a no-op placeholder to align local migrations with the
    # existing database state that already predates tracked migrations.
    pass


def downgrade():
    # No-op: this placeholder does not change schema.
    pass
