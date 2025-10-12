from flask import Blueprint

# Import blueprints from submodules so they register when this package is imported
from .auth_routes import auth_bp
from .admin_routes import admin_bp
from .course_routes import course_bp
from .assessment_routes import assessment_bp
from .lesson_routes import lesson_bp
from .ai_routes import ai_bp
from .file_routes import file_bp

# Export a list of blueprints to register in the main app
blueprints = [
    auth_bp,
    admin_bp,
    course_bp,
    assessment_bp,
    lesson_bp,
    ai_bp,
    file_bp,
]