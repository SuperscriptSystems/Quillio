from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy import types
import json

def get_json_type():
    """
    Returns a JSON type that works with the current database.
    Uses JSONB for PostgreSQL, falls back to Text type with JSON serialization for other databases.
    """
    try:
        from sqlalchemy.dialects.postgresql import JSONB
        return JSONB
    except ImportError:
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

        return JSONEncodedDict
