from flask_login import current_user
from app.models import db

def update_token_count(tokens_to_add):
    """Helper function to add tokens to the current user's total."""
    if tokens_to_add > 0:
        current_user.tokens_used += tokens_to_add
        db.session.commit()
