from flask import Flask
from flask_session import Session
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_migrate import Migrate
import math
import os

# --- App Initialization and Configuration ---
app = Flask(__name__, template_folder='../templates')
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY")
app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get('CONNECTION_STRING')
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"


db = SQLAlchemy(app)
migrate = Migrate(app, db)

Session(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

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