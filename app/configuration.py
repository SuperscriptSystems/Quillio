from flask import Flask
from flask_session import Session
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_migrate import Migrate
from flask_wtf.csrf import CSRFProtect, generate_csrf
import math
import os
from datetime import timedelta
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env file
env_path = Path('..') / '.env'
load_dotenv(env_path)

# --- App Initialization and Configuration ---
app = Flask(__name__, template_folder='../templates', static_folder="../static")

# Secret key
app.config['SECRET_KEY'] = "wdsadwfioji2ihhhdfuiah82"  # replace with os.environ.get('SECRET_KEY') in prod

# Database config
if os.environ.get('DATABASE_URL'):
    app.config['SQLALCHEMY_DATABASE_URI'] = os.environ['DATABASE_URL'].replace('postgres://', 'postgresql://', 1)
else:
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///quillio.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Session config
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"

# Email config
app.config['MAIL_SERVER'] = os.getenv('MAIL_SERVER')
app.config['MAIL_PORT'] = int(os.getenv('MAIL_PORT', 587))
app.config['MAIL_USE_TLS'] = os.getenv('MAIL_USE_TLS', 'true').lower() == 'true'
app.config['MAIL_USE_SSL'] = os.getenv('MAIL_USE_SSL', 'false').lower() == 'true'
app.config['MAIL_USERNAME'] = os.getenv('MAIL_USERNAME')
app.config['MAIL_PASSWORD'] = os.getenv('MAIL_PASSWORD')
app.config['MAIL_DEFAULT_SENDER'] = os.getenv('MAIL_DEFAULT_SENDER')

# Flask-Login config
app.config['REMEMBER_COOKIE_NAME'] = 'remember_token'
app.config['REMEMBER_COOKIE_DURATION'] = timedelta(days=30)
app.config['REMEMBER_COOKIE_PATH'] = '/'
app.config['REMEMBER_COOKIE_HTTPONLY'] = True
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(days=30)
app.config['SESSION_COOKIE_NAME'] = 'session'
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SECURE'] = os.environ.get('FLASK_ENV') == 'production'
app.config['SESSION_PROTECTION'] = 'strong'

# Initialize extensions
db = SQLAlchemy()
migrate = Migrate()
csrf = CSRFProtect()
login_manager = LoginManager()
Session(app)

db.init_app(app)
migrate.init_app(app, db)
csrf.init_app(app)
login_manager.init_app(app)
login_manager.login_view = 'login'
login_manager.refresh_view = 'login'
login_manager.needs_refresh_message = u"Session timed out, please re-login"
login_manager.needs_refresh_message_category = "info"

# CSRF token available in all templates
@app.context_processor
def inject_csrf_token():
    return dict(csrf_token=generate_csrf())

# --- Utility Filters ---
@app.template_filter('shorten_title')
def shorten_title(title, max_words=6):
    """Shorten a title to be more concise while keeping it meaningful."""
    if not title:
        return title

    replacements = {
        'introduction to ': '',
        'introduction: ': '',
        'introduction ': '',
        'the complete guide to ': '',
        'complete guide to ': '',
        'guide to ': '',
        'learn ': '',
        'learning ': '',
        'fundamentals of ': '',
        'basics of ': '',
        'how to ': '',
        'mastering ': '',
        'ultimate ': '',
        'comprehensive ': ''
    }

    import re
    title_lower = title.lower()
    for old, new in replacements.items():
        title_lower = re.sub(r'\b' + re.escape(old) + r'\b', new, title_lower, flags=re.IGNORECASE)

    words = title_lower.title().split()

    if len(words) > max_words:
        words = words[:max_words]
        last_word = words[-1].rstrip('.,;:')
        if last_word != words[-1]:
            words[-1] = last_word

    return ' '.join(words)

@app.context_processor
def inject_utility_functions():
    return dict(math=math, shorten_title=shorten_title)

# --- Import models ---
from app import models

# --- Register Blueprints ---
from app.routes import blueprints

for bp in blueprints:
    app.register_blueprint(bp)
