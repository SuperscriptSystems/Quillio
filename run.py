from dotenv import load_dotenv
load_dotenv()

from app.configuration import app, db
from flask import Flask
from app.models import User, Course, Lesson


if __name__ == "__main__":
    app.run(debug=True, port=8000)