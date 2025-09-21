from sqlalchemy import types, event
from sqlalchemy.engine import Engine
import json

class JSONEncodedDict(types.TypeDecorator):
    """Represents an immutable structure as a json-encoded string."""
    impl = types.Text

    def process_bind_param(self, value, dialect):
        if value is not None:
            value = json.dumps(value)
        return value

    def process_result_value(self, value, dialect):
        if value is not None:
            value = json.loads(value)
        return value

def get_json_type():
    """
    Returns a JSON type that works with the current database.
    Uses JSONB for PostgreSQL, falls back to Text type with JSON serialization for other databases.
    """
    from sqlalchemy import create_engine
    from sqlalchemy.engine.url import make_url
    
    # Get the database URL from environment variable or use default SQLite
    import os
    from dotenv import load_dotenv
    load_dotenv()
    
    db_url = os.environ.get('DATABASE_URL', 'sqlite:///quillio.db')
    
    if 'postgresql' in db_url:
        try:
            from sqlalchemy.dialects.postgresql import JSONB
            return JSONB
        except ImportError:
            return JSONEncodedDict
    return JSONEncodedDict

# This enables JSON1 extension for SQLite if available
@event.listens_for(Engine, 'connect')
def set_sqlite_pragma(dbapi_connection, connection_record):
    if 'sqlite' in str(dbapi_connection):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()
