from flask import Flask
from flask_session import Session
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
import tempfile
import math
import os
# --- App Initialization and Configuration ---
app = Flask(__name__, template_folder='../templates')
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY")
app.config["SQLALCHEMY_DATABASE_URI"] = 'postgresql://postgres:postgres@localhost:5432/arcane_db'
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
app.config["SESSION_FILE_DIR"] = tempfile.mkdtemp()
db = SQLAlchemy(app)
Session(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'


''' The following imports are there to run the code in models.py and routes.py.
     - models.py defines database models and the user loader for Flask-Login.
     - routes.py registers all the @app.route endpoints with the Flask app.'''
from app import models
from app import routes

@app.context_processor
def inject_utility_functions():
    ''' Makes the Python 'math' module available inside Jinja2 templates.
             Example:
                 Python:
                    return render_template("hello.html", username="John Doe")
                 Html:
                    <h1>Hello, {{ username }}!</h1>
                 Output:
                    <h1>Hello, John Doe!</h1>
         '''
    return dict(math=math)
