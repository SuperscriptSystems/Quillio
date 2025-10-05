from app.utils.password_validator import validate_password_strength, format_password_errors_for_flash
from app.models import User
from app import db

def change_user_password(user: User, current_password: str, new_password: str) -> tuple[bool, str]:
    """
    Change the user's password if valid.
    Returns (success, message)
    """
    if not user.check_password(current_password):
        return False, "Current password is incorrect."

    valid, errors = validate_password_strength(new_password)
    if not valid:
        return False, format_password_errors_for_flash(errors, getattr(user, "language", "english"))

    user.set_password(new_password)
    db.session.commit()
    return True, "Your password has been changed successfully!"
