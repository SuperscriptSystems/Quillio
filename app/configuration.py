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

@app.context_processor
def inject_utility_functions():
    return dict(math=math)