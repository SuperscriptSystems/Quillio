from flask import Blueprint, render_template, redirect, url_for, flash, jsonify, request
from flask_login import login_required, current_user
from app.models import Course, Lesson, CourseShare
from app.configuration import db
import secrets
from datetime import datetime, timedelta

course_bp = Blueprint('course', __name__)


@course_bp.route('/create')
@login_required
def home():
    return render_template('index.html')


@course_bp.route('/course_dashboard')
@login_required
def course_dashboard():
    active_courses = Course.query.filter_by(user_id=current_user.id, status='active').order_by(Course.id.desc()).all()
    return render_template('course_dashboard.html', courses=active_courses)


@course_bp.route('/settings', methods=['GET', 'POST'])
@login_required
def settings():
    if request.method == 'POST':
        current_user.preferred_lesson_length = int(request.form.get('lesson_length'))
        current_user.language = request.form.get('language')
        age = request.form.get('age')
        current_user.age = int(age) if age else None
        current_user.bio = request.form.get('bio')
        db.session.commit()
        flash('Your settings have been updated!', 'success')
        return redirect(url_for('course.settings'))
    return render_template('settings.html')


@course_bp.route('/course/<uuid:course_id>')
@course_bp.route('/course/<uuid:course_id>/<token>', methods=['GET'])
def show_course(course_id, token=None):
    course = Course.query.get_or_404(course_id)
    user = None
    if token:
        user = None
        try:
            # Preserve current behavior: token-based user verification is delegated to model
            user = None
        except Exception:
            user = None
    if not user and not current_user.is_authenticated:
        flash("Please log in to view this course.", "info")
        return redirect(url_for('auth.login', next=request.url))
    user = user or current_user
    # continue original logic in separate function or keep simple render
    return render_template('course_view.html', course=course)


@course_bp.route('/course/<uuid:course_id>/duplicate', methods=['POST'])
@login_required
def duplicate_course(course_id):
    original_course = Course.query.get_or_404(course_id)
    try:
        new_course = Course(
            user_id=current_user.id,
            course_title=f"{original_course.course_title} (Copy)",
            course_data=original_course.course_data,
            status='active',
            completed_lessons=0
        )
        db.session.add(new_course)
        db.session.flush()
        original_lessons = Lesson.query.filter_by(course_id=original_course.id).all()
        for lesson in original_lessons:
            new_lesson = Lesson(
                course_id=new_course.id,
                unit_title=lesson.unit_title,
                lesson_title=lesson.lesson_title,
                html_content=lesson.html_content,
                is_completed=False
            )
            db.session.add(new_lesson)
        db.session.commit()
        flash('Course has been added to your dashboard!', 'success')
        return jsonify({'success': True, 'redirect_url': url_for('course.show_course', course_id=new_course.id)})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500


@course_bp.route('/share-course', methods=['POST'])
@login_required
def share_course():
    data = request.get_json()
    course_id = data.get('course_id')
    if not course_id:
        return jsonify({'success': False, 'error': 'Missing course_id'}), 400
    try:
        course = Course.query.get(course_id)
        if not course or course.user_id != current_user.id:
            return jsonify({'success': False, 'error': 'Course not found or access denied'}), 404
        share = CourseShare.query.filter(
            CourseShare.course_id == course_id,
            CourseShare.created_by == current_user.id,
            CourseShare.expires_at > datetime.utcnow(),
            CourseShare.is_active == True
        ).first()
        if not share:
            share_token = secrets.token_urlsafe(16)
            share = CourseShare(
                course_id=course_id,
                token=share_token,
                created_by=current_user.id,
                expires_at=datetime.utcnow() + timedelta(days=30)
            )
            db.session.add(share)
            db.session.commit()
        share_link = url_for('course.public_course', course_id=course_id, token=share.token, _external=True)
        return jsonify({'success': True, 'share_link': share_link, 'course_title': course.course_title})
    except Exception as e:
        app.logger.error(f'Error in share_course: {str(e)}')
        return jsonify({'success': False, 'error': 'Internal server error'}), 500


@course_bp.route('/course/public/<uuid:course_id>', methods=['GET'])
def public_course(course_id):
    token = request.args.get('token')
    if not token:
        flash('This is a private course. Please log in to view it.', 'info')
        return redirect(url_for('auth.login', next=request.url))
    share = CourseShare.query.filter(
        CourseShare.course_id == str(course_id),
        CourseShare.token == token,
        CourseShare.expires_at > datetime.utcnow(),
        CourseShare.is_active == True
    ).first()
    if not share:
        flash('Invalid or expired share link', 'error')
        return redirect(url_for('auth.login'))
    course = Course.query.get_or_404(course_id)
    return render_template('public_course.html', course=course, share_link=request.url, is_owner=False)
