"""
Admin utilities for Quillio
Provides decorators and functions for admin-only functionality
"""

from functools import wraps
from flask import flash, redirect, url_for
from flask_login import current_user


def admin_required(f):
    """
    Decorator to require admin privileges for a route.
    Redirects non-admin users to dashboard with error message.
    """

    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            flash('Please log in to access this page.', 'warning')
            return redirect(url_for('login'))

        if not current_user.is_admin():
            flash('Admin privileges required to access this page.', 'danger')
            return redirect(url_for('course_dashboard'))

        return f(*args, **kwargs)

    return decorated_function


def get_available_models():
    """
    Get list of available AI models for admin selection.
    Returns dict with model names and descriptions.
    """
    return {
        'gpt-4': {
            'name': 'GPT-4',
            'description': 'Most capable model, best for complex course generation',
            'type': 'openai'
        },
        'gpt-3.5-turbo': {
            'name': 'GPT-3.5 Turbo',
            'description': 'Fast and efficient, good for most content generation',
            'type': 'openai'
        },
        'claude-3-sonnet': {
            'name': 'Claude 3 Sonnet',
            'description': 'Excellent for educational content and detailed explanations',
            'type': 'anthropic'
        },
        'claude-3-haiku': {
            'name': 'Claude 3 Haiku',
            'description': 'Fast and cost-effective for basic content generation',
            'type': 'anthropic'
        }
    }