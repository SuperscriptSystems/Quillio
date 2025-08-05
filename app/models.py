from app.configuration import db, login_manager  # Import your db and login_manager
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from sqlalchemy.dialects.postgresql import JSONB

class User(UserMixin, db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    preferred_lesson_length = db.Column(db.Integer, nullable=False, default=15)
    language = db.Column(db.String(10), nullable=False, default='english')

    tokens_used = db.Column(db.Integer, nullable=False, default=0)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

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
