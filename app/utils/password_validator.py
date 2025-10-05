"""
Password validation utility for Quillio.
Provides functions to validate, score, and format password requirements.
"""

import re
from typing import List, Tuple


# --- Core Validation Functions ---

def validate_password_strength(password: str) -> Tuple[bool, List[str]]:
    """
    Validate password strength according to Quillio security requirements.

    Returns a tuple: (is_valid, list_of_error_messages)
    """
    errors = []

    # Minimum length
    if len(password) < 8:
        errors.append("Password must be at least 8 characters long")

    # Character requirements
    if not re.search(r'[A-Z]', password):
        errors.append("Password must contain at least one uppercase letter (A-Z)")
    if not re.search(r'[a-z]', password):
        errors.append("Password must contain at least one lowercase letter (a-z)")
    if not re.search(r'[0-9]', password):
        errors.append("Password must contain at least one number (0-9)")
    if not re.search(r'[!@#$%^&*()_+\-=\[\]{}|;:,.<>?]', password):
        errors.append(
            "Password must contain at least one special symbol (!@#$%^&*()_+-=[]{}|;:,.<>?)"
        )

    # Weak/common passwords
    common_passwords = {'password', '12345678', 'qwerty123', 'admin123'}
    if password.lower() in common_passwords:
        errors.append("Password is too common and easily guessable")

    # Sequential characters
    seq_pattern = r'(012|123|234|345|456|567|678|789|890|' \
                  r'abc|bcd|cde|def|efg|fgh|ghi|hij|ijk|jkl|klm|' \
                  r'lmn|mno|nop|opq|pqr|qrs|rst|stu|tuv|uvw|vwx|wxy|xyz)'
    if re.search(seq_pattern, password.lower()):
        errors.append("Password should not contain sequential characters")

    is_valid = not errors
    return is_valid, errors


def get_password_requirements() -> List[str]:
    """
    Return a list of password requirements for display to users.
    """
    return [
        "At least 8 characters long",
        "At least one uppercase letter (A-Z)",
        "At least one lowercase letter (a-z)",
        "At least one number (0-9)",
        "At least one special symbol (!@#$%^&*()_+-=[]{}|;:,.<>?)"
    ]


# --- Password Strength Scoring ---

def get_password_strength_score(password: str) -> int:
    """
    Calculate a password strength score (0-100) based on length and variety.
    """
    score = 0

    # Length scoring
    if len(password) >= 8:
        score += 20
    if len(password) >= 12:
        score += 10
    if len(password) >= 16:
        score += 10

    # Character variety
    char_types = 0
    if re.search(r'[a-z]', password):
        score += 15
        char_types += 1
    if re.search(r'[A-Z]', password):
        score += 15
        char_types += 1
    if re.search(r'[0-9]', password):
        score += 15
        char_types += 1
    if re.search(r'[!@#$%^&*()_+\-=\[\]{}|;:,.<>?]', password):
        score += 15
        char_types += 1

    # Bonus for multiple character types
    if char_types >= 3:
        score += 10

    return min(score, 100)


# --- User-Friendly Formatting ---

def format_password_errors_for_flash(errors: List[str], language: str = 'english') -> str:
    """
    Format password validation errors for display in Flask flash messages.
    Supports English and Russian translations.
    """
    if not errors:
        return ""

    if language.lower() == 'russian':
        header = "Пароль не соответствует требованиям безопасности:"
        bullet = "• "
        translations = {
            "Password must be at least 8 characters long": "Пароль должен содержать не менее 8 символов",
            "Password must contain at least one uppercase letter (A-Z)": "Пароль должен содержать хотя бы одну заглавную букву (A-Z)",
            "Password must contain at least one lowercase letter (a-z)": "Пароль должен содержать хотя бы одну строчную букву (a-z)",
            "Password must contain at least one number (0-9)": "Пароль должен содержать хотя бы одну цифру (0-9)",
            "Password must contain at least one special symbol (!@#$%^&*()_+-=[]{}|;:,.<>?)": "Пароль должен содержать хотя бы один специальный символ (!@#$%^&*()_+-=[]{}|;:,.<>?)",
            "Password is too common and easily guessable": "Пароль слишком простой и легко угадывается",
            "Password should not contain sequential characters": "Пароль не должен содержать последовательные символы"
        }
        error_list = "\n".join([f"{bullet}{translations.get(err, err)}" for err in errors])
    else:
        header = "Password does not meet security requirements:"
        bullet = "• "
        error_list = "\n".join([f"{bullet}{err}" for err in errors])

    return f"{header}\n{error_list}"
