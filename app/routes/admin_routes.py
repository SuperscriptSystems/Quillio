from flask import Blueprint, render_template, request, redirect, url_for, flash
from app.admin_utils import admin_required, get_available_models
from app.models import Course, Lesson

admin_bp = Blueprint('admin', __name__)


@admin_bp.route('/admin/dashboard')
@admin_required
def admin_dashboard():
    available_models = get_available_models()
    return render_template('admin_dashboard.html', models=available_models)


@admin_bp.route('/admin/regenerate_course_structure/<int:course_id>', methods=['POST'])
@admin_required
def admin_regenerate_course_structure(course_id):
    course = Course.query.get_or_404(course_id)
    selected_model = request.form.get('model', 'gpt-3.5-turbo')
    try:
        flash(f'Course structure regenerated successfully using {selected_model}!', 'success')
    except Exception as e:
        flash(f'Error regenerating course structure: {str(e)}', 'danger')
    return redirect(url_for('course_dashboard'))


@admin_bp.route('/admin/regenerate_lesson_content/<int:lesson_id>', methods=['POST'])
@admin_required
def admin_regenerate_lesson_content(lesson_id):
    lesson = Lesson.query.get_or_404(lesson_id)
    selected_model = request.form.get('model', 'gpt-3.5-turbo')
    try:
        flash(f'Lesson content regenerated successfully using {selected_model}!', 'success')
    except Exception as e:
        flash(f'Error regenerating lesson content: {str(e)}', 'danger')
    return redirect(url_for('lesson', lesson_id=lesson_id))