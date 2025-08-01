from app.configuration import app, db
from app.models import User, Course, Lesson

if __name__ == '__main__':
    with app.app_context():
        db.create_all()  # This will create tables for all imported models
    app.run(debug=True)
