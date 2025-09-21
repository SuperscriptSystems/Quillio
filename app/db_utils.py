from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.types import JSON as JSONType

def get_json_type():
    """
    Returns the appropriate JSON type based on the database dialect.
    Uses JSONB for PostgreSQL and JSON for other databases like SQLite.
    """
    from flask import current_app
    from sqlalchemy import event
    from sqlalchemy.engine import Engine
    
    # For SQLAlchemy operations that don't have app context
    if not current_app:
        return JSONType()
        
    if current_app.config.get('SQLALCHEMY_DATABASE_URI', '').startswith('postgresql'):
        return JSONB()
    return JSONType()
