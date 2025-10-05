from flask import Blueprint, request, redirect, url_for, flash
from flask_login import login_required, current_user
from app.file_services import create_course_from_file_service

file_bp = Blueprint('file', __name__)


@file_bp.route('/upload_course', methods=['POST'])
@login_required
def upload_course():
    if 'file' not in request.files:
        flash('No file selected', 'danger')
        return redirect(url_for('course.home'))
    file = request.files['file']
    if file.filename == '':
        flash('No file selected', 'danger')
        return redirect(url_for('course.home'))
    try:
        instructions = request.form.get('instructions', '')
        include_background = request.form.get('include_background') == '1'
        new_course, error = create_course_from_file_service(file=file, user=current_user, instructions=instructions, include_background=include_background)
        if error:
            flash(f'Error creating course: {error}', 'danger')
            return redirect(url_for('course.home'))
        flash(f'Course "{new_course.course_title}" created successfully from uploaded file!', 'success')
        return redirect(url_for('course.show_course', course_id=new_course.id))
    except Exception as e:
        flash(f'Error processing file: {str(e)}', 'danger')
        return redirect(url_for('course.home'))

