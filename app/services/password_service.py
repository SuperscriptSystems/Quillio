from werkzeug.security import generate_password_hash, check_password_hash
from flask import flash, redirect, url_for, session
from functools import wraps

def change_user_password(user, current_password, new_password, confirm_password):
    """
    Change the user's password after verifying the current password.
    
    Args:
        user: The user object whose password needs to be changed
        current_password (str): The user's current password
        new_password (str): The new password
        confirm_password (str): Confirmation of the new password
        
    Returns:
        tuple: (success (bool), message (str))
    """
    if not check_password_hash(user.password, current_password):
        return False, "Current password is incorrect"
        
    if new_password != confirm_password:
        return False, "New passwords do not match"
        
    if len(new_password) < 8:
        return False, "Password must be at least 8 characters long"
        
    # Update the password
    user.password = generate_password_hash(new_password)
    return True, "Password updated successfully"

def login_required(f):
    """
    Decorator to ensure a user is logged in.
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please log in to access this page.', 'warning')
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    return decorated_function

def admin_required(f):
    """
    Decorator to ensure the logged-in user is an admin.
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'is_admin' not in session or not session['is_admin']:
            flash('You do not have permission to access this page.', 'danger')
            return redirect(url_for('main.index'))
        return f(*args, **kwargs)
    return decorated_function
