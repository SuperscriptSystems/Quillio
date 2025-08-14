from app.configuration import app, db
from flask import Flask
from app.models import User, Course, Lesson

with app.app_context():
    db.create_all()

if __name__ == "__main__":
    app.run(debug=True)
