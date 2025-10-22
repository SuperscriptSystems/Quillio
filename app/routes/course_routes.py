from flask import Blueprint, render_template, redirect, url_for, flash, jsonify, request, current_app
from flask_login import login_required, current_user
from app.models import Course, Lesson, CourseShare
from app.configuration import db
from sqlalchemy.orm import joinedload
import secrets
from datetime import datetime, timedelta

course_bp = Blueprint('course', __name__)


@course_bp.route('/')
def index():
    """Root route - redirect to appropriate page based on authentication status"""
    if current_user.is_authenticated:
        return redirect(url_for('course.course_dashboard'))
    return redirect(url_for('auth.login'))


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
    # Build a lookup of lessons by title for this course so the template can resolve IDs and completion
    all_lessons = Lesson.query.filter_by(course_id=course.id).all()
    lessons_by_title = {l.lesson_title: l for l in all_lessons}
    # Scores per unit may be optional; provide an empty dict by default
    scores = {}
    return render_template('course.html', course=course, course_obj=course, all_lessons=lessons_by_title, scores=scores, course_id=course.id, is_course_complete=course.completed_lessons >= len([l for u in course.course_data.get('units', []) for l in u.get('lessons', [])]) if course.course_data else False)


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
        return jsonify({'success': True, 'share_link': share_link, 'course_title': course.course_title})
    except Exception as e:
        return jsonify({'success': False, 'error': 'Internal server error'}), 500


@course_bp.route('/course/public/<uuid:course_id>', methods=['GET'])
def public_course(course_id):
    # Get the token from query parameters
    token = request.args.get('token')
    
    # If no token provided, redirect to login
    if not token:
        flash('This is a private course. Please log in to view it.', 'info')
        return redirect(url_for('auth.login', next=request.url))
    
    # Find the active share record
    share = CourseShare.query.filter(
        CourseShare.course_id == str(course_id),
        CourseShare.token == token,
        CourseShare.expires_at > datetime.utcnow(),
        CourseShare.is_active == True
    ).first()
    
    # If no valid share found, show error
    if not share:
        flash('Invalid or expired share link', 'error')
        return redirect(url_for('auth.login'))
    
    # Get the course with its lessons
    course = Course.query.options(
        joinedload(Course.lessons)
    ).get_or_404(course_id)
    
    # Group lessons by unit_title
    units = {}
    for lesson in course.lessons:
        if lesson.unit_title not in units:
            units[lesson.unit_title] = []
        units[lesson.unit_title].append({
            'id': lesson.id,
            'lesson_title': lesson.lesson_title,
            'is_completed': lesson.is_completed,
            'html_content': lesson.html_content
        })
    
    # Convert to list of units with lessons for the template
    units_list = [{'unit_title': title, 'lessons': lessons} 
                 for title, lessons in units.items()]
    
    # Initialize course description
    description = None
    
    # Check if description exists in course_data JSON
    if hasattr(course, 'course_data') and isinstance(course.course_data, dict):
        description = course.course_data.get('description')
    
    # If no description, try to generate one with AI
    if not description or description == 'No description available.':
        try:
            # Get all lessons for the course
            lesson_titles = [lesson.lesson_title for lesson in course.lessons]
            
            # Create prompt for AI
            prompt = f"""Create a concise, engaging course description (2-3 sentences) for a course titled \"{course.course_title}\".
            
            Course Content:
            {', '.join(lesson_titles) if lesson_titles else 'No lessons available.'}
            
            The description should be professional, highlight key learning outcomes, and encourage enrollment.
            """
            
            # Call AI to generate description
            from app.ai_clients import _call_gemini
            
            try:
                ai_description, _ = _call_gemini(prompt)
                if ai_description:
                    description = ai_description.strip()
                    # Store in course_data if it exists
                    if hasattr(course, 'course_data') and isinstance(course.course_data, dict):
                        if course.course_data is None:
                            course.course_data = {}
                        course.course_data['description'] = description
                        db.session.commit()
            except Exception as e:
                current_app.logger.error(f"Error generating AI description: {str(e)}")
                description = 'Course description not available.'
        except Exception as e:
            current_app.logger.error(f"Error in description generation: {str(e)}")
            description = 'Course description not available.'
    
    # If we still don't have a description, set a default
    if not description:
        description = 'No description available.'
    
    # Calculate total lessons
    total_lessons = len(course.lessons)
    
    # Add description to course data if it doesn't exist
    if not hasattr(course, 'description'):
        course.description = description
    elif not course.description:
        course.description = description
    
    # Render the public course template
    return render_template('public_course.html', 
                         course=course, 
                         units=units_list,
                         total_lessons=total_lessons,
                         token=token)


@course_bp.route('/course/<uuid:course_id>/certificate')
@login_required
def show_certificate(course_id):
    from app.models import User
    return redirect(url_for('course.public_certificate', course_id=course_id, token=current_user.get_auth_token()))


@course_bp.route('/public/certificate/<uuid:course_id>')
@course_bp.route('/public/certificate/<uuid:course_id>/<token>', methods=['GET'])
def public_certificate(course_id, token=None):
    from app.models import User
    # Get the course first
    course = Course.query.get_or_404(course_id)
    
    # Check if user is accessing via valid token
    user = None
    if token:
        user = User.verify_auth_token(token)
    
    # If no valid token and user is not logged in, redirect to login
    if not user and not current_user.is_authenticated:
        flash("Please log in to view this certificate.", "info")
        return redirect(url_for('auth.login', next=request.url))
    
    # Use the token user if available, otherwise use the current user
    user = user or current_user
    
    # Check if the course is completed
    total_lessons = Lesson.query.filter_by(course_id=course.id).count()
    if not (total_lessons > 0 and course.completed_lessons == total_lessons):
        flash("This course is not yet completed.", "warning")
        if current_user.is_authenticated and current_user.id == course.user_id:
            return redirect(url_for('course.show_course', course_id=course_id))
        return redirect(url_for('course.home'))
    
    # Allow access if:
    # 1. The user is the course owner
    # 2. The user is an admin
    # 3. The request includes a valid share token
    is_owner = user and user.id == course.user_id
    is_admin = current_user.is_authenticated and current_user.is_admin
    has_valid_token = token is not None and user is not None
    
    if not (is_owner or is_admin or has_valid_token):
        flash("You don't have permission to view this certificate.", "danger")
        return redirect(url_for('course.home'))
    
    completion_date = datetime.now().strftime("%B %d, %Y")
    completion_score = 100  # Default to 100% for now
    
    # Generate shareable link
    share_token = user.get_auth_token(expires_in=60*60*24*365)  # 1 year expiration
    share_link = url_for('course.public_certificate', course_id=course_id, token=share_token, _external=True)
    
    # Generate course link with token if needed
    if token and (not current_user.is_authenticated or current_user.id != course.user_id):
        course_link = url_for('course.show_course', course_id=course_id, token=token, _external=True)
    else:
        course_link = url_for('course.show_course', course_id=course_id, _external=True)
    
    return render_template('certificate.html',
                         user_name=user.full_name or user.email.split('@')[0],
                         course_title=course.course_title,
                         completion_date=completion_date,
                         completion_score=completion_score,
                         share_link=share_link,
                         course_link=course_link,
                         show_share_options=current_user.is_authenticated and current_user.id == user.id)