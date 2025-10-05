"""
Quillio application database models.
Includes User, Course, Lesson, UnitTestResult, CourseShare.
"""

import uuid
import random
from datetime import datetime, timedelta

import jwt
from flask import current_app
from flask_login import UserMixin
from sqlalchemy.types import TypeDecorator, CHAR
from sqlalchemy.dialects.postgresql import UUID as PostgresUUID

from app.configuration import db, login_manager
from app.db_utils import get_json_type
from werkzeug.security import generate_password_hash, check_password_hash


# --- GUID Type for Cross-DB UUID Support ---
class GUID(TypeDecorator):
    """Platform-independent GUID type.

    Uses PostgreSQL UUID type, otherwise stores as CHAR(32) string.
    """
    impl = CHAR
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == 'postgresql':
            return dialect.type_descriptor(PostgresUUID())
        return dialect.type_descriptor(CHAR(32))

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        if isinstance(value, str):
            try:
                if len(value) == 32 and all(c in '0123456789abcdef' for c in value.lower()):
                    value = uuid.UUID(hex=value)
                else:
                    value = uuid.UUID(value)
            except (ValueError, AttributeError):
                return value
        if isinstance(value, uuid.UUID):
            return str(value) if dialect.name == 'postgresql' else "%.32x" % value.int
        return value

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        if isinstance(value, uuid.UUID):
            return value
        if isinstance(value, str) and len(value) == 32 and all(c in '0123456789abcdef' for c in value.lower()):
            return uuid.UUID(hex=value)
        try:
            return uuid.UUID(str(value))
        except (ValueError, AttributeError, TypeError):
            return value


# --- User Model ---
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
    is_verified = db.Column(db.Boolean, nullable=False, default=False)
    verification_token = db.Column(db.String(100), nullable=True)
    token_expires_at = db.Column(db.DateTime, nullable=True)
    reset_token = db.Column(db.String(100), unique=True, nullable=True)
    reset_token_expires = db.Column(db.DateTime, nullable=True)
    is_quillio_admin = db.Column(db.Boolean, nullable=False, default=False)

    # --- Password ---
    def set_password(self, password: str):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        return check_password_hash(self.password_hash, password)

    @property
    def is_admin(self) -> bool:
        return self.is_quillio_admin

    # --- JWT Authentication ---
    def get_auth_token(self, expires_in: int = 3600) -> str:
        payload = {
            'user_id': str(self.id),
            'exp': datetime.utcnow() + timedelta(seconds=expires_in)
        }
        return jwt.encode(payload, current_app.config['SECRET_KEY'], algorithm='HS256')

    @staticmethod
    def verify_auth_token(token: str):
        try:
            data = jwt.decode(token, current_app.config['SECRET_KEY'], algorithms=['HS256'])
            return db.session.get(User, uuid.UUID(data['user_id']))
        except (jwt.PyJWTError, ValueError, AttributeError):
            return None

    # --- Email Verification ---
    def generate_verification_code(self) -> str:
        self.verification_token = str(random.randint(100000, 999999))
        self.token_expires_at = datetime.utcnow() + timedelta(hours=24)
        return self.verification_token

    def verify_email_code(self, code: str) -> bool:
        if (self.verification_token == str(code) and
                self.token_expires_at and datetime.utcnow() < self.token_expires_at):
            self.is_verified = True
            self.verification_token = None
            self.token_expires_at = None
            return True
        return False

    # --- Password Reset ---
    def generate_password_reset_code(self) -> str:
        self.reset_token = str(random.randint(100000, 999999))
        self.reset_token_expires = datetime.utcnow() + timedelta(hours=1)
        return self.reset_token

    def verify_reset_code(self, code: str) -> bool:
        if (self.reset_token == str(code) and
                self.reset_token_expires and datetime.utcnow() < self.reset_token_expires):
            self.reset_token = None
            self.reset_token_expires = None
            return True
        return False


# --- Course Model ---
class Course(db.Model):
    __tablename__ = 'courses'

    id = db.Column(GUID(), primary_key=True, default=uuid.uuid4)
    user_id = db.Column(GUID(), db.ForeignKey('users.id'), nullable=False)
    course_title = db.Column(db.String(200), nullable=False)
    course_data = db.Column(get_json_type(), nullable=False)
    status = db.Column(db.String(50), nullable=False, default='active')
    completed_lessons = db.Column(db.Integer, nullable=False, default=0)

    user = db.relationship('User', backref=db.backref('courses', lazy=True, cascade='all, delete-orphan'))


# --- Lesson Model ---
class Lesson(db.Model):
    __tablename__ = 'lessons'

    id = db.Column(GUID(), primary_key=True, default=uuid.uuid4)
    course_id = db.Column(GUID(), db.ForeignKey('courses.id'), nullable=False)
    unit_title = db.Column(db.String, nullable=False)
    lesson_title = db.Column(db.String, nullable=False)
    html_content = db.Column(db.Text, nullable=True)
    is_completed = db.Column(db.Boolean, default=False, nullable=False)

    course = db.relationship('Course', backref=db.backref('lessons', lazy=True, cascade='all, delete-orphan'))


# --- Unit Test Results ---
class UnitTestResult(db.Model):
    __tablename__ = 'unit_test_results'

    id = db.Column(GUID(), primary_key=True, default=uuid.uuid4)
    user_id = db.Column(GUID(), db.ForeignKey('users.id'), nullable=False)
    course_id = db.Column(GUID(), db.ForeignKey('courses.id'), nullable=False)
    unit_title = db.Column(db.String, nullable=False)
    score = db.Column(db.Integer, nullable=False)

    user = db.relationship('User', backref=db.backref('unit_test_results', lazy=True, cascade='all, delete-orphan'))
    course = db.relationship('Course', backref=db.backref('unit_test_results', lazy=True, cascade='all, delete-orphan'))

    __table_args__ = (db.UniqueConstraint('user_id', 'course_id', 'unit_title', name='_user_course_unit_uc'),)


# --- Course Sharing ---
class CourseShare(db.Model):
    __tablename__ = 'course_shares'

    id = db.Column(GUID(), primary_key=True, default=uuid.uuid4)
    course_id = db.Column(GUID(), db.ForeignKey('courses.id'), nullable=False)
    token = db.Column(db.String(32), unique=True, nullable=False)
    created_by = db.Column(GUID(), db.ForeignKey('users.id'), nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    expires_at = db.Column(db.DateTime, nullable=False)
    is_active = db.Column(db.Boolean, default=True, nullable=False)

    course = db.relationship('Course', backref=db.backref('shares', lazy=True))
    created_by_user = db.relationship('User', backref=db.backref('shared_courses', lazy=True))

    def is_valid(self) -> bool:
        return self.is_active and datetime.utcnow() < self.expires_at


# --- Flask-Login Loader ---
@login_manager.user_loader
def load_user(user_id: str):
    return User.query.get(user_id)
