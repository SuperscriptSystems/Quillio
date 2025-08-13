from app.configuration import app, db
from app.models import User, Course, Lesson

with app.app_context():
    db.create_all()
