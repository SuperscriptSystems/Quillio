"""
Password validation utility for Quillio
Enforces strong password requirements on the backend
"""

import re
from typing import Tuple, List


def validate_password_strength(password: str) -> Tuple[bool, List[str]]:
    """
    Validate password strength according to Quillio security requirements.
    
    Requirements:
    - At least 8 characters long
    - At least one uppercase letter (A-Z)
    - At least one lowercase letter (a-z)
    - At least one number (0-9)
    - At least one special symbol (!@#$%^&*()_+-=[]{}|;:,.<>?)
    
    Args:
        password (str): The password to validate
        
    Returns:
        Tuple[bool, List[str]]: (is_valid, list_of_error_messages)
    """
    errors = []
    
    # Check minimum length
    if len(password) < 8:
        errors.append("Password must be at least 8 characters long")
    
    # Check for uppercase letter
    if not re.search(r'[A-Z]', password):
        errors.append("Password must contain at least one uppercase letter (A-Z)")
    
    # Check for lowercase letter
    if not re.search(r'[a-z]', password):
        errors.append("Password must contain at least one lowercase letter (a-z)")
    
    # Check for number
    if not re.search(r'[0-9]', password):
        errors.append("Password must contain at least one number (0-9)")
    
    # Check for special character
    if not re.search(r'[!@#$%^&*()_+\-=\[\]{}|;:,.<>?]', password):
        errors.append("Password must contain at least one special symbol (!@#$%^&*()_+-=[]{}|;:,.<>?)")
    
    # Check for common weak patterns
    if password.lower() in ['password', '12345678', 'qwerty123', 'admin123']:
        errors.append("Password is too common and easily guessable")
    
    # Check for sequential characters
    if re.search(r'(012|123|234|345|456|567|678|789|890|abc|bcd|cde|def|efg|fgh|ghi|hij|ijk|jkl|klm|lmn|mno|nop|opq|pqr|qrs|rst|stu|tuv|uvw|vwx|wxy|xyz)', password.lower()):
        errors.append("Password should not contain sequential characters")
    
    is_valid = len(errors) == 0
    return is_valid, errors


def get_password_requirements() -> List[str]:
    """
    Get a list of password requirements for display to users.
    
    Returns:
        List[str]: List of password requirement descriptions
    """
    return [
        "At least 8 characters long",
        "At least one uppercase letter (A-Z)",
        "At least one lowercase letter (a-z)", 
        "At least one number (0-9)",
        "At least one special symbol (!@#$%^&*()_+-=[]{}|;:,.<>?)"
    ]


def get_password_strength_score(password: str) -> int:
    """
    Calculate password strength score from 0-100.
    
    Args:
        password (str): The password to score
        
    Returns:
        int: Strength score from 0-100
    """
    score = 0
    
    # Length scoring
    if len(password) >= 8:
        score += 20
    if len(password) >= 12:
        score += 10
    if len(password) >= 16:
        score += 10
    
    # Character variety scoring
    if re.search(r'[a-z]', password):
        score += 15
    if re.search(r'[A-Z]', password):
        score += 15
    if re.search(r'[0-9]', password):
        score += 15
    if re.search(r'[!@#$%^&*()_+\-=\[\]{}|;:,.<>?]', password):
        score += 15
    
    # Bonus for multiple character types
    char_types = 0
    if re.search(r'[a-z]', password):
        char_types += 1
    if re.search(r'[A-Z]', password):
        char_types += 1
    if re.search(r'[0-9]', password):
        char_types += 1
    if re.search(r'[!@#$%^&*()_+\-=\[\]{}|;:,.<>?]', password):
        char_types += 1
    
    if char_types >= 3:
        score += 10
    
    return min(score, 100)


def format_password_errors_for_flash(errors: List[str], language: str = 'english') -> str:
    """
    Format password validation errors for Flask flash messages.
    
    Args:
        errors (List[str]): List of error messages
        language (str): Language for error messages ('english' or 'russian')
        
    Returns:
        str: Formatted error message
    """
    if not errors:
        return ""
    
    if language == 'russian':
        header = "Пароль не соответствует требованиям безопасности:"
        bullet = "• "
        
        # Translate common error messages to Russian
        russian_translations = {
            "Password must be at least 8 characters long": "Пароль должен содержать не менее 8 символов",
            "Password must contain at least one uppercase letter (A-Z)": "Пароль должен содержать хотя бы одну заглавную букву (A-Z)",
            "Password must contain at least one lowercase letter (a-z)": "Пароль должен содержать хотя бы одну строчную букву (a-z)",
            "Password must contain at least one number (0-9)": "Пароль должен содержать хотя бы одну цифру (0-9)",
            "Password must contain at least one special symbol (!@#$%^&*()_+-=[]{}|;:,.<>?)": "Пароль должен содержать хотя бы один специальный символ (!@#$%^&*()_+-=[]{}|;:,.<>?)",
            "Password is too common and easily guessable": "Пароль слишком простой и легко угадывается",
            "Password should not contain sequential characters": "Пароль не должен содержать последовательные символы"
        }
        
        translated_errors = [russian_translations.get(error, error) for error in errors]
        error_list = "\n".join([f"{bullet}{error}" for error in translated_errors])
    else:
        header = "Password does not meet security requirements:"
        bullet = "• "
        error_list = "\n".join([f"{bullet}{error}" for error in errors])
    
    return f"{header}\n{error_list}"
