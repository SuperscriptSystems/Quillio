from flask import Flask
from flask_session import Session
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_migrate import Migrate
from flask_wtf.csrf import CSRFProtect, generate_csrf
import math
import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env file
env_path = Path('..') / '.env'
load_dotenv(env_path)

# --- App Initialization and Configuration ---
app = Flask(__name__, template_folder='../templates', static_folder="../static")
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY')

# Use PostgreSQL if available, otherwise fall back to SQLite
if os.environ.get('DATABASE_URL'):
    app.config['SQLALCHEMY_DATABASE_URI'] = os.environ['DATABASE_URL'].replace('postgres://', 'postgresql://', 1)
else:
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///quillio.db'
    
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"

# Email configuration
app.config['MAIL_SERVER'] = os.getenv('MAIL_SERVER')
app.config['MAIL_PORT'] = int(os.getenv('MAIL_PORT', 587))
app.config['MAIL_USE_TLS'] = os.getenv('MAIL_USE_TLS', 'true').lower() == 'true'
app.config['MAIL_USE_SSL'] = os.getenv('MAIL_USE_SSL', 'false').lower() == 'true'
app.config['MAIL_USERNAME'] = os.getenv('MAIL_USERNAME')
app.config['MAIL_PASSWORD'] = os.getenv('MAIL_PASSWORD')
app.config['MAIL_DEFAULT_SENDER'] = os.getenv('MAIL_DEFAULT_SENDER')

# Initialize extensions
db = SQLAlchemy()
migrate = Migrate()
csrf = CSRFProtect()
login_manager = LoginManager()

# Initialize extensions with app
db.init_app(app)
migrate.init_app(app, db)
csrf.init_app(app)
login_manager.init_app(app)
login_manager.login_view = 'login'
Session(app)

# Add CSRF token to all templates
@app.context_processor
def inject_csrf_token():
    return dict(csrf_token=generate_csrf())

from app import models
from app import routes


@app.template_filter('shorten_title')
def shorten_title(title, max_words=6):
    """Shorten a title to be more concise while keeping it meaningful."""
    if not title:
        return title
    
    # Common phrases to remove or replace
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
    
    # Apply replacements
    import re
    title_lower = title.lower()
    for old, new in replacements.items():
        title_lower = re.sub(r'\b' + re.escape(old) + r'\b', new, title_lower, flags=re.IGNORECASE)
    
    # Capitalize first letter of each word for the final title
    words = title_lower.title().split()
    
    # Keep only the first few words if the title is still long
    if len(words) > max_words:
        words = words[:max_words]
        # Remove any trailing punctuation
        last_word = words[-1].rstrip('.,;:')
        if last_word != words[-1]:
            words[-1] = last_word
    
    return ' '.join(words)

@app.context_processor
def inject_utility_functions():
    return dict(math=math, shorten_title=shorten_title)