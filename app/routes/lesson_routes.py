from flask import Blueprint, render_template, redirect, url_for, Response, stream_with_context, request, flash
from flask_login import login_required, current_user
from app.models import Lesson, Course
from app.services import generate_lesson_content_service
from app.configuration import db

lesson_bp = Blueprint('lesson', __name__)


@lesson_bp.route('/loading/lesson/<uuid:lesson_id>')
@login_required
def loading_lesson(lesson_id):
    lesson = db.session.get(Lesson, lesson_id)
    if not lesson or lesson.course.user_id != current_user.id:
        return redirect(url_for('course.course_dashboard'))
    if lesson.html_content:
        if not lesson.is_completed:
            lesson.is_completed = True
            course = lesson.course
            course.completed_lessons = Lesson.query.filter_by(course_id=course.id, is_completed=True).count()
            db.session.commit()
        return redirect(url_for('lesson.show_lesson', lesson_id=lesson.id))
    return render_template('lesson_stream.html', lesson=lesson)


@lesson_bp.route('/stream_lesson_data/<uuid:lesson_id>')
@login_required
def stream_lesson_data(lesson_id):
    lesson = db.session.get(Lesson, lesson_id)
    if not lesson or lesson.course.user_id != current_user.id:
        return Response("Unauthorized", status=403)
    lesson_content_generator = generate_lesson_content_service(lesson, current_user)
    return Response(stream_with_context(lesson_content_generator), mimetype='text/plain')
