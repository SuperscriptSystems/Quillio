from app.configuration import db, login_manager
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from sqlalchemy.dialects.postgresql import JSONB
import secrets
import random
from datetime import datetime, timedelta

class User(UserMixin, db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
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

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)
    
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
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    course_title = db.Column(db.String(200), nullable=False)
    course_data = db.Column(JSONB, nullable=False)
    status = db.Column(db.String(50), nullable=False, default='active')
    completed_lessons = db.Column(db.Integer, nullable=False, default=0)
    user = db.relationship('User', backref=db.backref('courses', lazy=True, cascade='all, delete-orphan'))

class Lesson(db.Model):
    __tablename__ = 'lessons'
    id = db.Column(db.Integer, primary_key=True)
    course_id = db.Column(db.Integer, db.ForeignKey('courses.id'), nullable=False)
    unit_title = db.Column(db.String, nullable=False)
    lesson_title = db.Column(db.String, nullable=False)
    html_content = db.Column(db.Text, nullable=True)
    is_completed = db.Column(db.Boolean, default=False, nullable=False)
    course = db.relationship('Course', backref=db.backref('lessons', lazy=True, cascade="all, delete-orphan"))

class UnitTestResult(db.Model):
    __tablename__ = 'unit_test_results'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    course_id = db.Column(db.Integer, db.ForeignKey('courses.id'), nullable=False)
    unit_title = db.Column(db.String, nullable=False)
    score = db.Column(db.Integer, nullable=False)

    user = db.relationship('User', backref=db.backref('unit_test_results', lazy=True, cascade="all, delete-orphan"))
    course = db.relationship('Course', backref=db.backref('unit_test_results', lazy=True, cascade="all, delete-orphan"))

    __table_args__ = (db.UniqueConstraint('user_id', 'course_id', 'unit_title', name='_user_course_unit_uc'),)

@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))