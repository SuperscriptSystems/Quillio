from app.configuration import db, login_manager
from .db_utils import get_json_type
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.dialects.postgresql import UUID as PostgresUUID
from sqlalchemy.types import TypeDecorator, CHAR
import uuid
import secrets
import random
from datetime import datetime, timedelta
import jwt
from flask import current_app

class GUID(TypeDecorator):
    """Platform-independent GUID type.
    Uses PostgreSQL's UUID type, otherwise uses
    CHAR(32), storing as stringified hex values.
    """
    impl = CHAR
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == 'postgresql':
            return dialect.type_descriptor(PostgresUUID())
        else:
            return dialect.type_descriptor(CHAR(32))

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
            
        # Convert to UUID if it's a string
        if isinstance(value, str):
            try:
                # Try to convert from hex string if it's a valid UUID hex
                if len(value) == 32 and all(c in '0123456789abcdef' for c in value.lower()):
                    value = uuid.UUID(hex=value)
                else:
                    # Try to convert from standard UUID string
                    value = uuid.UUID(value)
            except (ValueError, AttributeError):
                # If it's not a valid UUID string, treat it as a regular string ID
                return value
        
        # Handle UUID object
        if isinstance(value, uuid.UUID):
            if dialect.name == 'postgresql':
                return str(value)
            return "%.32x" % value.int
            
        # Fallback for other types (like integer IDs)
        return value

    def process_result_value(self, value, dialect):
        if value is None:
            return value
            
        # If it's already a UUID, return as is
        if isinstance(value, uuid.UUID):
            return value
            
        # If it's a 32-character hex string (SQLite)
        if isinstance(value, str) and len(value) == 32 and all(c in '0123456789abcdef' for c in value.lower()):
            return uuid.UUID(hex=value)
            
        try:
            # Try to convert from standard UUID string (PostgreSQL)
            return uuid.UUID(str(value))
        except (ValueError, AttributeError, TypeError):
            # If all else fails, return the value as is
            return value

class User(UserMixin, db.Model):
    __tablename__ = 'users'
    id = db.Column(GUID(), primary_key=True, default=uuid.uuid4)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    full_name = db.Column(db.String(120), nullable=True)
    preferred_lesson_length = db.Column(db.Integer, nullable=False, default=15)
    language = db.Column(db.String(10), nullable=False, default='english')

    age = db.Column(db.Integer, nullable=True)
    bio = db.Column(db.Text, nullable=True)

    tokens_used = db.Column(db.Integer, nullable=False, default=0)
    
    # Email verification fields
    is_verified = db.Column(db.Boolean, nullable=False, default=False)
    verification_token = db.Column(db.String(100), nullable=True)
    token_expires_at = db.Column(db.DateTime, nullable=True)

    # Password reset fields
    reset_token = db.Column(db.String(100), unique=True, nullable=True)
    reset_token_expires = db.Column(db.DateTime, nullable=True)

    # Admin privileges
    is_quillio_admin = db.Column(db.Boolean, nullable=False, default=False)
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def is_admin(self):
        """Check if user has admin privileges"""
        return self.is_quillio_admin
        
    def get_auth_token(self, expires_in=3600):
        """Generate a JWT token for authentication"""
        return jwt.encode(
            {'user_id': str(self.id), 'exp': datetime.utcnow() + timedelta(seconds=expires_in)},
            current_app.config['SECRET_KEY'],
            algorithm='HS256'
        )
        
    @staticmethod
    def verify_auth_token(token):
        """Verify JWT token and return user if valid"""
        try:
            data = jwt.decode(token, current_app.config['SECRET_KEY'], algorithms=['HS256'])
            return db.session.get(User, uuid.UUID(data['user_id']))
        except (jwt.PyJWTError, ValueError, AttributeError):
            return None

    def generate_verification_code(self):
        """Generate a new 6-digit email verification code that expires in 24 hours"""
        self.verification_token = str(random.randint(100000, 999999))
        self.token_expires_at = datetime.utcnow() + timedelta(hours=24)
        return self.verification_token
    
    def verify_email_code(self, code):
        """Verify email with the provided 6-digit code"""
        if (self.verification_token == str(code) and 
            self.token_expires_at and 
            datetime.utcnow() < self.token_expires_at):
            self.is_verified = True
            self.verification_token = None
            self.token_expires_at = None
            return True
        return False

class Course(db.Model):
    __tablename__ = 'courses'
    id = db.Column(GUID(), primary_key=True, default=uuid.uuid4)
    user_id = db.Column(GUID(), db.ForeignKey('users.id'), nullable=False)
    course_title = db.Column(db.String(200), nullable=False)
    course_data = db.Column(get_json_type(), nullable=False)
    status = db.Column(db.String(50), nullable=False, default='active')
    completed_lessons = db.Column(db.Integer, nullable=False, default=0)
    user = db.relationship('User', backref=db.backref('courses', lazy=True, cascade='all, delete-orphan'))

class Lesson(db.Model):
    __tablename__ = 'lessons'
    id = db.Column(GUID(), primary_key=True, default=uuid.uuid4)
    course_id = db.Column(GUID(), db.ForeignKey('courses.id'), nullable=False)
    unit_title = db.Column(db.String, nullable=False)
    lesson_title = db.Column(db.String, nullable=False)
    html_content = db.Column(db.Text, nullable=True)
    is_completed = db.Column(db.Boolean, default=False, nullable=False)
    course = db.relationship('Course', backref=db.backref('lessons', lazy=True, cascade="all, delete-orphan"))

class UnitTestResult(db.Model):
    __tablename__ = 'unit_test_results'
    id = db.Column(GUID(), primary_key=True, default=uuid.uuid4)
    user_id = db.Column(GUID(), db.ForeignKey('users.id'), nullable=False)
    course_id = db.Column(GUID(), db.ForeignKey('courses.id'), nullable=False)
    unit_title = db.Column(db.String, nullable=False)
    score = db.Column(db.Integer, nullable=False)

    user = db.relationship('User', backref=db.backref('unit_test_results', lazy=True, cascade="all, delete-orphan"))
    course = db.relationship('Course', backref=db.backref('unit_test_results', lazy=True, cascade="all, delete-orphan"))

    __table_args__ = (db.UniqueConstraint('user_id', 'course_id', 'unit_title', name='_user_course_unit_uc'),)

@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, user_id)