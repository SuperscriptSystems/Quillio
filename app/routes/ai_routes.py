from flask import Blueprint, request, jsonify, Response, stream_with_context
from flask_login import login_required, current_user
from app.configuration import db
from app.models import Lesson
from app.services import get_tutor_response_service, edit_course_service

ai_bp = Blueprint('ai', __name__)


@ai_bp.route('/chat_with_tutor', methods=['POST'])
@login_required
def chat_with_tutor():
    try:
        data = request.get_json()
    except Exception:
        return jsonify({"error": "Invalid JSON data"}), 400
    if not data:
        return jsonify({"error": "No data provided"}), 400
    lesson_id = data.get('lesson_id')
    user_question = data.get('message')
    chat_history = data.get('history', [])
    if not lesson_id or not user_question:
        return jsonify({"error": "Missing required fields: lesson_id and message are required"}), 400
    lesson = db.session.get(Lesson, str(lesson_id))
    if not lesson:
        return jsonify({"error": "Lesson not found"}), 404
    if lesson.course.user_id != current_user.id:
        return jsonify({"error": "Unauthorized access to this lesson"}), 403
    try:
        ai_response_generator = get_tutor_response_service(lesson, chat_history, user_question, current_user)
    except Exception:
        return jsonify({"error": "Failed to generate AI response"}), 500
    def generate():
        try:
            for chunk in ai_response_generator:
                yield chunk
        except Exception:
            yield "I'm sorry, I encountered a technical issue while generating a response. Please try again."
    return Response(stream_with_context(generate()), mimetype='text/plain')


@ai_bp.route('/edit_course/<uuid:course_id>', methods=['GET', 'POST'])
@login_required
def edit_course(course_id):
    from app.models import Course
    course = Course.query.get_or_404(course_id)
    if course.user_id != current_user.id:
        return jsonify({"success": False, "error": "Unauthorized"}), 403
    data = request.get_json()
    user_request = data.get('request')
    if not user_request:
        return jsonify({"success": False, "error": "No request provided."}), 400
    updated_course, error = edit_course_service(course, user_request, current_user.language)
    if error:
        return jsonify({"success": False, "error": error}), 500
    return jsonify({"success": True})

