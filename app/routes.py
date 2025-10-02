import secrets
from flask import render_template, request, session, redirect, url_for, jsonify, flash, Response, stream_with_context, make_response
from flask_wtf.csrf import generate_csrf
from flask_login import login_user, logout_user, login_required, current_user
import time
from app.forms import InitialAssessmentForm, AnswerForm, ForgotPasswordForm, VerificationForm, ResetPasswordForm
from app.admin_utils import admin_required, get_available_models
from datetime import datetime, timedelta
from app.forms import LoginForm, RegistrationForm, VerificationForm
from app.configuration import app, db
from app.models import User, Course, Lesson, UnitTestResult
from app.services import (
    generate_test_service,
    evaluate_answers_service,
    generate_knowledge_assessment_service,
    calculate_percentage_score_service,
    create_course_service,
    generate_lesson_content_service,
    get_tutor_response_service,
    edit_course_service,
)
from app.helpers import save_test_to_dict, load_test_from_dict, render_answer_input
from app.email_service import send_verification_email, send_resend_verification_email, send_password_reset_email
from app.file_services import create_course_from_file_service
from app.password_validator import validate_password_strength, format_password_errors_for_flash


@app.route('/admin/dashboard')
@admin_required
def admin_dashboard():
    """Admin dashboard with model selection and regeneration options"""
    available_models = get_available_models()
    return render_template('admin_dashboard.html', models=available_models)


@app.route('/admin/regenerate_course_structure/<int:course_id>', methods=['POST'])
@admin_required
def admin_regenerate_course_structure(course_id):
    """Regenerate course structure with admin-selected model"""
    course = Course.query.get_or_404(course_id)
    selected_model = request.form.get('model', 'gpt-3.5-turbo')

    try:
        # Use the selected model for regeneration
        # This would integrate with your existing course generation service
        # but pass the model parameter

        flash(f'Course structure regenerated successfully using {selected_model}!', 'success')
    except Exception as e:
        flash(f'Error regenerating course structure: {str(e)}', 'danger')

    return redirect(url_for('course_dashboard'))


@app.route('/admin/regenerate_lesson_content/<int:lesson_id>', methods=['POST'])
@admin_required
def admin_regenerate_lesson_content(lesson_id):
    """Regenerate lesson content with admin-selected model"""
    lesson = Lesson.query.get_or_404(lesson_id)
    selected_model = request.form.get('model', 'gpt-3.5-turbo')

    try:
        # Use the selected model for lesson regeneration
        # This would integrate with your existing lesson generation service
        # but pass the model parameter

        flash(f'Lesson content regenerated successfully using {selected_model}!', 'success')
    except Exception as e:
        flash(f'Error regenerating lesson content: {str(e)}', 'danger')

    return redirect(url_for('lesson', lesson_id=lesson_id))


# --- Authentication and Main Navigation Routes ---
@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('course_dashboard'))
    
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data).first()
        
        if user and user.check_password(form.password.data):
            if not user.is_verified:
                flash('Please verify your email before logging in. Check your inbox for the verification code.', 'warning')
                return redirect(url_for('verify_code', email=form.email.data))
            
            login_user(user, remember=form.remember.data)
            flash('Login successful!', 'success')
            next_page = request.args.get('next')
            return redirect(next_page or url_for('course_dashboard'))
        
        flash('Invalid email or password. Please try again.', 'danger')
    
    return render_template('login.html', title='Login', form=form)


@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('course_dashboard'))
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        full_name = request.form.get('full_name')
        lesson_length = request.form.get('lesson_length')
        age = request.form.get('age')
        bio = request.form.get('bio')

        # Basic validation
        if not email or not password or not full_name or not lesson_length:
            flash('Please fill in all required fields.', 'warning')
            return redirect(url_for('register'))

        if User.query.filter_by(email=email).first():
            flash('Email already exists.', 'warning')
            return redirect(url_for('register'))

        try:
            lesson_length_val = int(lesson_length)
        except (TypeError, ValueError):
            flash('Lesson length must be a number.', 'warning')
            return redirect(url_for('register'))

        # Create new user
        new_user = User(
            email=email,
            full_name=full_name.strip(),
            preferred_lesson_length=lesson_length_val,
            age=int(age) if age else None,
            bio=bio
        )
        new_user.set_password(password)

        # Generate verification code
        new_user.generate_verification_code()

        db.session.add(new_user)
        db.session.commit()

        # Send verification email
        if send_verification_email(new_user):
            flash('Registration successful! Please check your email for a 6-digit verification code.', 'success')
            return redirect(url_for('verify_code', email=email))
        else:
            flash('Registration successful, but we could not send the verification email. Please contact support.',
                  'warning')
            return redirect(url_for('login'))
    return render_template('register.html')


@app.route('/health', methods=['GET'])
def healthcheck():
    return "OK", 200


@app.route('/verify_code', methods=['GET', 'POST'])
def verify_code():
    """Email verification code entry route for registration"""
    form = VerificationForm()
    email = request.args.get('email')
    
    if email:
        form.email.data = email
    
    if form.validate_on_submit():
        email = form.email.data
        verification_code = form.verification_code.data
        user = User.query.filter_by(email=email).first()
        
        if not user:
            flash('Invalid verification request.', 'danger')
            return redirect(url_for('login'))
        
        if user.is_verified:
            flash('Your email is already verified. You can log in.', 'info')
            return redirect(url_for('login'))
        
        if user.verify_email_code(verification_code):
            db.session.commit()
            flash('Email verified successfully! You can now log in.', 'success')
            return redirect(url_for('login'))
        else:
            flash('Invalid or expired verification code. Please try again.', 'danger')
    
    return render_template('verify_code.html', 
                         email=email, 
                         verification_type='registration',
                         form=form)


@app.route('/login_verify_code', methods=['GET', 'POST'])
def login_verify_code():
    """Login verification code entry route"""
    form = VerificationForm()
    email = request.args.get('email')
    
    if email:
        form.email.data = email
    
    user = User.query.filter_by(email=email).first() if email else None
    if not user:
        flash('Invalid login request.', 'danger')
        return redirect(url_for('login'))
    
    if form.validate_on_submit():
        verification_code = form.verification_code.data
        if user.verify_email_code(verification_code):
            db.session.commit()
            login_user(user)
            flash('Login successful!', 'success')
            next_page = request.args.get('next')
            return redirect(next_page or url_for('course_dashboard'))
        else:
            flash('Invalid verification code. Please try again.', 'danger')
    
    return render_template('verify_code.html', 
                         email=email, 
                         verification_type='login',
                         form=form)


@app.route('/resend_verification', methods=['GET', 'POST'])
def resend_verification():
    """Resend verification email"""
    if request.method == 'POST':
        email = request.form.get('email')
        user = User.query.filter_by(email=email).first()
        
        # Don't reveal if the email exists for security
        if user and not user.is_verified:
            user.generate_verification_code()
            db.session.commit()
            send_verification_email(user)
            flash('Verification code sent! Please check your inbox.', 'success')
            return redirect(url_for('verify_code', email=email))
        
        # Show success message even if email doesn't exist (security)
        flash('If an account exists with this email, a verification code has been sent.', 'info')
        return redirect(url_for('login'))
    
    # Pre-fill email if user is logged in but not verified
    email = current_user.email if current_user.is_authenticated else ''
    return render_template('resend_verification.html', email=email)


@app.route('/logout')
@login_required
def logout():
    # First, clear the user's session
    session.clear()
    
    # Create the response first
    resp = make_response(redirect(url_for('login')))
    
    # Clear all possible session and auth cookies
    cookie_names = [
        'session',
        'remember_token',
        'session-',  # Flask-Session uses 'session-{id}'
        'flask',
        app.config.get('SESSION_COOKIE_NAME', 'session'),
        app.config.get('REMEMBER_COOKIE_NAME', 'remember_token')
    ]
    
    # Clear all cookies we can think of
    for name in cookie_names:
        resp.set_cookie(name, '', expires=0, path='/', httponly=True)
    
    # Clear Flask-Login cookies with all possible variations
    cookie_domains = [None, app.config.get('SESSION_COOKIE_DOMAIN')]
    for domain in cookie_domains:
        resp.set_cookie(
            app.config.get('REMEMBER_COOKIE_NAME', 'remember_token'),
            '',
            expires=0,
            path=app.config.get('REMEMBER_COOKIE_PATH', '/'),
            domain=domain,
            secure=app.config.get('REMEMBER_COOKIE_SECURE', False),
            httponly=True
        )
        resp.set_cookie(
            app.config.get('SESSION_COOKIE_NAME', 'session'),
            '',
            expires=0,
            path=app.config.get('SESSION_COOKIE_PATH', '/'),
            domain=domain,
            secure=app.config.get('SESSION_COOKIE_SECURE', False),
            httponly=True
        )
    
    # Finally, log the user out
    logout_user()
    
    # Clear the session again for good measure
    from flask import session as flask_session
    flask_session.clear()
    
    flash('You have been successfully logged out.', 'info')
    return resp


@app.route('/create')
@login_required
def home():
    return render_template('index.html')


@app.route('/course_dashboard')
@login_required
def course_dashboard():
    active_courses = Course.query.filter_by(user_id=current_user.id, status='active').order_by(Course.id.desc()).all()
    return render_template('course_dashboard.html', courses=active_courses)


@app.route('/settings', methods=['GET', 'POST'])
@login_required
def settings():
    if request.method == 'POST':
        current_user.preferred_lesson_length = int(request.form.get('lesson_length'))
        current_user.language = request.form.get('language')

        # Handle optional age and bio fields
        age = request.form.get('age')
        current_user.age = int(age) if age else None
        current_user.bio = request.form.get('bio')

        db.session.commit()
        flash('Your settings have been updated!', 'success')
        return redirect(url_for('settings'))
    return render_template('settings.html')


# --- Course and Lesson Routes ---
@app.route('/course/<uuid:course_id>')
@app.route('/course/<uuid:course_id>/<token>', methods=['GET'])
def show_course(course_id, token=None):
    course = Course.query.get_or_404(course_id)
    
    # Check for valid token
    user = None
    if token:
        user = User.verify_auth_token(token)
    
    # If no valid token and user is not logged in, redirect to login
    if not user and not current_user.is_authenticated:
        flash("Please log in to view this course.", "info")
        return redirect(url_for('login', next=request.url))
    
    # Use the token user if available, otherwise use the current user
    user = user or current_user
    
    # Check permissions
    is_owner = user and user.id == course.user_id
    is_admin = current_user.is_authenticated and current_user.is_admin
    has_valid_token = token is not None and user is not None
    
    if not (is_owner or is_admin or has_valid_token):
        flash("You don't have permission to view this course.", "danger")
        return redirect(url_for('home'))

    lessons = Lesson.query.filter_by(course_id=course.id).all()
    total_lessons = len(lessons)
    
    # Get all test results for this course and user
    test_results = UnitTestResult.query.filter_by(user_id=current_user.id, course_id=course_id).all()
    total_tests = len(test_results)
    completed_tests = len([r for r in test_results if r.score is not None])
    
    # Course is complete only if all lessons and all tests are completed
    is_course_complete = (total_lessons > 0 and 
                         course.completed_lessons == total_lessons and
                         total_tests > 0 and 
                         completed_tests == total_tests)

    lessons_dict = {lesson.lesson_title: lesson for lesson in lessons}
    scores_dict = {result.unit_title: result.score for result in test_results}

    return render_template('course.html',
                           course_obj=course,
                           course=course.course_data,
                           course_id=course_id,
                           all_lessons=lessons_dict,
                           scores=scores_dict,
                           is_course_complete=is_course_complete)


@app.route('/course/<uuid:course_id>/archive', methods=['POST'])
@login_required
def archive_course(course_id):
    course = Course.query.get_or_404(course_id)
    if course.user_id == current_user.id:
        course.status = 'archived'
        db.session.commit()
        flash(f"'{course.course_title}' has been archived.", "info")
    return redirect(url_for('course_dashboard'))


@app.route('/lesson/<uuid:lesson_id>')
@login_required
def show_lesson(lesson_id):
    lesson = db.session.get(Lesson, lesson_id)
    if not lesson or not lesson.html_content or lesson.course.user_id != current_user.id:
        flash("Lesson not found or not yet generated.", "warning")
        return redirect(url_for('course_dashboard'))

    return render_template('lesson_page.html',
                           title=lesson.lesson_title,
                           content=lesson.html_content,
                           course_id=lesson.course_id,
                           lesson_id=lesson.id)


@app.route('/course/<uuid:course_id>/certificate')
@login_required
def show_certificate(course_id):
    return redirect(url_for('public_certificate', course_id=course_id, token=current_user.get_auth_token()))

@app.route('/public/certificate/<uuid:course_id>')
@app.route('/public/certificate/<uuid:course_id>/<token>', methods=['GET'])
def public_certificate(course_id, token=None):
    # Get the course first
    course = Course.query.get_or_404(course_id)
    
    # Check if user is accessing via valid token
    user = None
    if token:
        user = User.verify_auth_token(token)
    
    # If no valid token and user is not logged in, redirect to login
    if not user and not current_user.is_authenticated:
        flash("Please log in to view this certificate.", "info")
        return redirect(url_for('login', next=request.url))
    
    # Use the token user if available, otherwise use the current user
    user = user or current_user
    
    # Check if the course is completed
    total_lessons = Lesson.query.filter_by(course_id=course.id).count()
    if not (total_lessons > 0 and course.completed_lessons == total_lessons):
        flash("This course is not yet completed.", "warning")
        if current_user.is_authenticated and current_user.id == course.user_id:
            return redirect(url_for('show_course', course_id=course_id))
        return redirect(url_for('home'))
    
    # Allow access if:
    # 1. The user is the course owner
    # 2. The user is an admin
    # 3. The request includes a valid share token
    is_owner = user and user.id == course.user_id
    is_admin = current_user.is_authenticated and current_user.is_admin()
    has_valid_token = token is not None and user is not None
    
    if not (is_owner or is_admin or has_valid_token):
        flash("You don't have permission to view this certificate.", "danger")
        return redirect(url_for('home'))
    
    completion_date = dt.now().strftime("%B %d, %Y")
    completion_score = 100  # Default to 100% for now, can be calculated based on test results if available
    
    # Generate shareable link
    share_token = user.get_auth_token(expires_in=60*60*24*365)  # 1 year expiration
    share_link = url_for('public_certificate', course_id=course_id, token=share_token, _external=True)
    
    # Generate course link with token if needed
    if token and (not current_user.is_authenticated or current_user.id != course.user_id):
        course_link = url_for('show_course', course_id=course_id, token=token, _external=True)
    else:
        course_link = url_for('show_course', course_id=course_id, _external=True)
    
    return render_template('certificate.html',
                         user_name=user.full_name or user.email.split('@')[0],
                         course_title=course.course_title,
                         completion_date=completion_date,
                         completion_score=completion_score,
                         share_link=share_link,
                         course_link=course_link,
                         show_share_options=current_user.is_authenticated and current_user.id == user.id)

@app.route('/course/<uuid:course_id>/duplicate', methods=['POST'])
@login_required
def duplicate_course(course_id):
    # Get the original course
    original_course = Course.query.get_or_404(course_id)
    
    try:
        # Create a new course for the current user
        new_course = Course(
            user_id=current_user.id,
            course_title=f"{original_course.course_title} (Copy)",
            course_data=original_course.course_data,
            status='active',
            completed_lessons=0
        )
        
        db.session.add(new_course)
        db.session.flush()  # Get the new course ID
        
        # Duplicate all lessons
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
        return jsonify({
            'success': True,
            'redirect_url': url_for('show_course', course_id=new_course.id)
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/share-certificate', methods=['POST'])
@login_required
def share_certificate():
    data = request.get_json()
    email = data.get('email')
    certificate_url = data.get('certificate_url')
    course_title = data.get('course_title', 'a course')
    
    if not email or not certificate_url:
        return jsonify({'success': False, 'error': 'Missing required fields'}), 400
    
    try:
        subject = f"{current_user.full_name or current_user.email.split('@')[0]} shared a Quillio certificate with you"
        body = f"""Hello!

{current_user.full_name or current_user.email.split('@')[0]} has shared their Quill.io certificate for "{course_title}" with you.

View the certificate here: {certificate_url}

Best regards,
The Quill.io Team"""
        
        # Send email (implement your email sending function here)
        # Example: send_email(email, subject, body)
        
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

    return render_template('certificate.html',
                           user_name=(current_user.full_name or current_user.email),
                           course_title=course.course_title,
                           completion_date=completion_date)


# --- Initial Assessment Routes ---
@app.route('/assessment', methods=['GET', 'POST'])
@login_required
def assessment():
    # If the test exists in session, show current question
    if 'test' in session:
        test = load_test_from_dict(session['test'])
        current_index = session.get('index', 0)
        
        # Check if we've completed all questions
        if current_index >= len(test.questions):
            return redirect(url_for('loading', context='results'))
            
        current_question = test.questions[current_index]

        form = AnswerForm()
        # Convert options dictionary to list of (value, text) tuples
        form.answer.choices = [(key, value) for key, value in current_question.options.items()]

        if form.validate_on_submit():
            if 'answers' not in session:
                session['answers'] = []
                
            # Get the selected option text from the form choices
            selected_option = next((text for value, text in form.answer.choices 
                                 if value == form.answer.data), form.answer.data)
            
            session['answers'].append({
                'question': current_question.question,
                'answer': selected_option,
                'answer_value': form.answer.data  # Store the original value as well
            })
            session['index'] = current_index + 1
            session.modified = True  # Ensure the session is saved

            if session['index'] < len(test.questions):
                return redirect(url_for('assessment'))
            else:
                return redirect(url_for('loading', context='results'))

        return render_template('assessment.html', form=form, test=test, index=current_index)

    # If no test exists, show initial assessment form
    form = InitialAssessmentForm()
    if form.validate_on_submit():
        topic = form.topic.data
        knowledge = form.knowledge.data

        additional_context = f"User claims to be {knowledge}/100 in their knowledge of the topic."
        user_profile = {'age': current_user.age, 'bio': current_user.bio}

        test = generate_test_service(topic, "multiple_choice", additional_context,
                                     current_user.language, user_profile=user_profile)
        if not test:
            flash("There was an error generating the test. Please try again.", "danger")
            return redirect(url_for('home'))

        session['test'] = save_test_to_dict(test)
        session['answers'] = []
        session['index'] = 0
        return redirect(url_for('assessment'))

    return render_template('assessment.html', form=form)




@app.route('/test_ready')
@login_required
def test_ready():
    if 'test' not in session: return redirect(url_for('home'))
    return render_template('test_ready.html', lang=current_user.language)


@app.route('/results')
@login_required
def show_results():
    if 'assessed_answers' not in session: 
        return redirect(url_for('home'))
    
    return render_template('results.html',
                           answers=session['assessed_answers'],
                           knowledge_assessment=session.get('knowledge_assessment'),
                           course_id=session.get('current_course_id'),
                           lang=current_user.language)


# --- Loading and Data Fetching Routes ---
@app.route('/loading/<context>')
@login_required
def loading(context):
    lang = current_user.language
    message = ''
    fetch_url = ''
    if context == 'results':
        message = "Анализируем ваши ответы и создаем персональный курс..." if lang == 'russian' else "Analyzing your answers and generating your personalized course..."
        fetch_url = url_for('get_results_data')
    elif context == 'unit_results':
        message = "Анализируем ваши ответы..." if lang == 'russian' else "Analyzing your answers..."
        fetch_url = url_for('get_unit_results_data')
    else:
        return redirect(url_for('home'))
    return render_template('loading.html', message=message, fetch_url=fetch_url, lang=lang)


@app.route('/get_results_data')
@login_required
def get_results_data():
    test = load_test_from_dict(session['test'])
    detailed_results = evaluate_answers_service(test.questions, session['answers'], current_user.language)

    if not detailed_results:
        flash("There was an error evaluating your test answers. Please try again.", "danger")
        for key in ['test', 'answers', 'index']: session.pop(key, None)
        return jsonify({'redirect_url': url_for('home')})

    knowledge_assessment = generate_knowledge_assessment_service(detailed_results)

    if "Error:" in knowledge_assessment or "Unauthorized" in knowledge_assessment:
        flash(
            "Your test was graded, but we could not generate a course. The API key is invalid or your account has billing issues. Please check your credentials.",
            "danger")
        session['assessed_answers'] = detailed_results
        session['knowledge_assessment'] = "Could not be generated due to an API authentication error."
        for key in ['test', 'answers', 'index', 'current_course_id']: session.pop(key, None)
        return jsonify({'redirect_url': url_for('show_results')})

    new_course = create_course_service(current_user, test.topic, knowledge_assessment, detailed_results)

    if not new_course:
        flash("We're sorry, but we couldn't create your course at this time. Please try again later.", "danger")
        return jsonify({'redirect_url': url_for('home')})

    session['assessed_answers'] = detailed_results
    session['knowledge_assessment'] = knowledge_assessment
    session['current_course_id'] = new_course.id
    for key in ['test', 'answers', 'index']: session.pop(key, None)

    return jsonify({'redirect_url': url_for('show_results')})


@app.route('/loading/lesson/<uuid:lesson_id>')
@login_required
def loading_lesson(lesson_id):
    lesson = db.session.get(Lesson, lesson_id)
    if not lesson  or lesson.course.user_id != current_user.id:
        return redirect(url_for('course_dashboard'))

    # If content already exists, just show it. Also mark as complete if it's not.
    if lesson.html_content:
        if not lesson.is_completed:
            lesson.is_completed = True
            course = lesson.course
            course.completed_lessons = Lesson.query.filter_by(course_id=course.id, is_completed=True).count()
            db.session.commit()
        return redirect(url_for('show_lesson', lesson_id=lesson.id))

    # Otherwise, render the streaming page
    return render_template('lesson_stream.html', lesson=lesson)


@app.route('/stream_lesson_data/<uuid:lesson_id>')
@login_required
def stream_lesson_data(lesson_id):
    lesson = db.session.get(Lesson, lesson_id)
    if not lesson or lesson.course.user_id != current_user.id:
        return Response("Unauthorized", status=403)

    lesson_content_generator = generate_lesson_content_service(lesson, current_user)

    return Response(stream_with_context(lesson_content_generator), mimetype='text/plain')


# --- Unit Test Routes ---
@app.route('/loading/unit_test/<uuid:course_id>/<unit_title>/<test_title>')
@login_required
def loading_unit_test(course_id, unit_title, test_title):
    course = Course.query.get_or_404(course_id)
    if course.user_id != current_user.id:
        flash("You do not have permission to start this test.", "danger")
        return redirect(url_for('course_dashboard'))

    lang = current_user.language
    message = f"Готовим ваш тест для {unit_title}..." if lang == 'russian' else f"Preparing your test for {unit_title}..."
    fetch_url = url_for('get_unit_test_data', course_id=course_id, unit_title=unit_title, test_title=test_title)
    return render_template('loading.html', message=message, fetch_url=fetch_url, lang=lang)


@app.route('/get_unit_test_data/<uuid:course_id>/<unit_title>/<test_title>')
@login_required
def get_unit_test_data(course_id, unit_title, test_title):
    course = Course.query.get_or_404(course_id)
    if course.user_id != current_user.id:
        return jsonify({"error": "Unauthorized"}), 403

    # Check if all lessons in this unit are completed
    lessons_in_unit = Lesson.query.filter_by(course_id=course_id, unit_title=unit_title).all()
    incomplete_lessons = [lesson.lesson_title for lesson in lessons_in_unit if not lesson.is_completed]
    
    if incomplete_lessons:
        lang = current_user.language
        if lang == 'russian':
            message = f"Пожалуйста, завершите все уроки в разделе {unit_title} перед прохождением теста. "
            message += f"Незавершённые уроки: {', '.join(incomplete_lessons)}"
        else:
            message = f"Please complete all lessons in {unit_title} before taking the test. "
            message += f"Incomplete lessons: {', '.join(incomplete_lessons)}"
        flash(message, "warning")
        return jsonify({'redirect_url': url_for('show_course', course_id=course_id)})

    # All lessons are completed, gather content for test context
    lesson_content_context = "\n\n".join([lesson.html_content for lesson in lessons_in_unit if lesson.html_content])

    topic = f"{unit_title}: {test_title}"
    user_profile = {'age': current_user.age, 'bio': current_user.bio}

    test = generate_test_service(topic, "multiple_choice", "Create 5-10 questions.", current_user.language,
                                 user_profile=user_profile, lesson_content_context=lesson_content_context)
    if not test:
        flash(f"Could not generate the test for {unit_title}. There may have been an issue with the AI service.",
              "danger")
        return jsonify({'redirect_url': url_for('show_course', course_id=course_id)})

    session['current_unit_test'] = save_test_to_dict(test)
    session['current_unit_test_index'] = 0
    session['current_unit_test_answers'] = []
    session['current_course_id'] = course_id
    session['current_unit_title'] = unit_title
    session.modified = True
    return jsonify({'redirect_url': url_for('unit_test')})


@app.route('/unit_test', methods=['GET', 'POST'])
@login_required
def unit_test():
    try:
        if 'current_unit_test' not in session:
            return redirect(url_for('course_dashboard'))
        
        test = load_test_from_dict(session['current_unit_test'])
        
        if 'current_unit_test_index' not in session:
            session['current_unit_test_index'] = 0
        if 'current_unit_test_answers' not in session:
            session['current_unit_test_answers'] = []
        
        test_index = session['current_unit_test_index']
        
        if request.method == 'POST':
            current_question = test.questions[test_index]
            form = AnswerForm()
            if hasattr(current_question, 'choices'):
                form.answer.choices = [(str(i), str(choice)) for i, choice in enumerate(current_question.choices)]
            
            if 'answer' in request.form:
                form.answer.data = request.form['answer']
                
                if form.answer.data is not None:
                    session['current_unit_test_answers'].append({
                        "question": current_question.question, 
                        "answer": form.answer.data,
                        "choices": getattr(current_question, 'choices', None)
                    })
                    
                    session['current_unit_test_index'] += 1
                    session.modified = True
                    
                    if session['current_unit_test_index'] >= len(test.questions):
                        return redirect(url_for('loading', context='unit_results'))
                    
                    return redirect(url_for('unit_test'))
            
            flash('Please select an answer before continuing.', 'error')
            return render_question(test, test_index, current_user.language)
        
        if test_index >= len(test.questions):
            return redirect(url_for('loading', context='unit_results'))
        
        return render_question(test, test_index, current_user.language)
        
    except Exception:
        flash('An error occurred while loading the test. Please try again.', 'error')
        return redirect(url_for('course_dashboard'))

def render_question(test, test_index, lang):
    """Helper function to render a question"""
    current_question = test.questions[test_index]
    
    form = AnswerForm()
    if hasattr(current_question, 'choices'):
        form.answer.choices = [(str(i), str(choice)) for i, choice in enumerate(current_question.choices)]
    
    input_html = render_answer_input(current_question)
    
    return render_template('question_page.html',
        test_page=current_question,
        input_html=input_html,
        current=test_index + 1,
        total=len(test.questions),
        form=form,
        lang=lang
    )


@app.route('/get_unit_results_data')
@login_required
def get_unit_results_data():
    if 'current_unit_test' not in session:
        return jsonify({"error": "No unit test in progress."}), 400

    test_info = load_test_from_dict(session['current_unit_test'])
    user_answers = session['current_unit_test_answers']
    course_id = session.get('current_course_id')
    unit_title = session.get('current_unit_title')

    detailed_results = evaluate_answers_service(test_info.questions, user_answers, current_user.language)
    time.sleep(1)
    final_score = calculate_percentage_score_service(detailed_results)

    if course_id and unit_title:
        existing_result = UnitTestResult.query.filter_by(
            user_id=current_user.id,
            course_id=course_id,
            unit_title=unit_title
        ).first()

        if existing_result:
            existing_result.score = final_score
        else:
            new_result = UnitTestResult(
                user_id=current_user.id,
                course_id=course_id,
                unit_title=unit_title,
                score=final_score
            )
            db.session.add(new_result)
        db.session.commit()

    session['unit_test_final_results'] = {
        'answers': detailed_results,
        'final_score': final_score,
        'test_name': test_info.test_name,
        'course_id': course_id
    }

    for key in ['current_unit_test', 'current_unit_test_index', 'current_unit_test_answers', 'current_course_id',
                'current_unit_title']:
        session.pop(key, None)

    return jsonify({'redirect_url': url_for('show_unit_test_results')})


@app.route('/unit_test_results')
@login_required
def show_unit_test_results():
    if 'unit_test_final_results' not in session:
        return redirect(url_for('course_dashboard'))

    results = session.pop('unit_test_final_results', None)
    if not results:
        return redirect(url_for('course_dashboard'))

    return render_template(
        'unit_test_results.html',
        answers=results['answers'],
        final_score=results['final_score'],
        test_name=results['test_name'],
        course_id=results['course_id']
    )


# --- Chat and AI Editing Routes ---
@app.route('/chat_with_tutor', methods=['POST'])
@login_required
def chat_with_tutor():
    print("\n" + "="*50)
    print("CHAT WITH TUTOR REQUEST")
    print("="*50)
    print(f"Current User: {current_user.id}")
    print("\nREQUEST HEADERS:")
    for k, v in request.headers.items():
        print(f"  {k}: {v}")
    
    raw_data = request.get_data()
    print("\nRAW REQUEST DATA:", raw_data)
    
    try:
        data = request.get_json()
        print("\nPARSED JSON DATA:", data)
    except Exception as e:
        print("\nERROR PARSING JSON:", str(e))
        return jsonify({"error": "Invalid JSON data"}), 400
    
    try:
        data = request.get_json()
        print(f"Request data: {data}")
        
        if not data:
            error_msg = "No data provided in request"
            print(error_msg)
            return jsonify({"error": error_msg}), 400
            
        lesson_id = data.get('lesson_id')
        user_question = data.get('message')
        chat_history = data.get('history', [])

        print(f"Lesson ID: {lesson_id}, Type: {type(lesson_id).__name__}")
        print(f"User Question: {user_question}")
        print(f"Chat History Length: {len(chat_history)}")

        if not lesson_id or not user_question:
            error_msg = f"Missing required fields. lesson_id: {lesson_id}, message: {bool(user_question)}"
            print(error_msg)
            return jsonify({"error": "Missing required fields: lesson_id and message are required"}), 400

        # Try to get the lesson with the ID as a string first
        lesson = db.session.get(Lesson, str(lesson_id))
        if not lesson:
            error_msg = f"Lesson not found with ID: {lesson_id} (type: {type(lesson_id).__name__})"
            print(error_msg)
            return jsonify({"error": "Lesson not found"}), 404
            
        print(f"Found lesson: {lesson.id}, Course ID: {lesson.course_id}, Owner ID: {lesson.course.user_id}")
            
        if lesson.course.user_id != current_user.id:
            error_msg = f"User {current_user.id} is not authorized to access lesson {lesson.id} (owner: {lesson.course.user_id})"
            print(error_msg)
            return jsonify({"error": "Unauthorized access to this lesson"}), 403

        try:
            print("Generating AI response...")
            ai_response_generator = get_tutor_response_service(lesson, chat_history, user_question, current_user)
            print("AI response generator created successfully")
        except Exception as e:
            error_msg = f"Error getting tutor response: {str(e)}"
            print(error_msg)
            import traceback
            traceback.print_exc()
            return jsonify({"error": "Failed to generate AI response"}), 500

        def generate():
            try:
                print("Starting response generation...")
                for chunk in ai_response_generator:
                    yield chunk
                print("\nResponse generation completed successfully")
            except Exception as e:
                error_msg = f"Error during response generation: {str(e)}"
                print(error_msg)
                import traceback
                traceback.print_exc()
                yield "I'm sorry, I encountered a technical issue while generating a response. Please try again."

        return Response(stream_with_context(generate()), mimetype='text/plain')
        
    except Exception as e:
        error_msg = f"Unexpected error in chat_with_tutor: {str(e)}"
        print(error_msg)
        import traceback
        traceback.print_exc()
        return jsonify({"error": "An unexpected error occurred. Please try again later."}), 500


@app.route('/edit_course/<uuid:course_id>', methods=['GET', 'POST'])
@login_required
def edit_course(course_id):
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


@app.route('/change_password', methods=['POST'])
@login_required
def change_password():
    # Check if user's email is verified
    if not current_user.is_verified:
        flash('Please verify your email before changing your password.', 'error')
        return redirect(url_for('settings'))

    current_password = request.form.get('current_password')
    new_password = request.form.get('new_password')
    confirm_password = request.form.get('confirm_password')

    # Validate current password
    if not current_user.check_password(current_password):
        flash('Current password is incorrect.', 'error')
        return redirect(url_for('settings'))

    # Validate new password
    if len(new_password) < 6:
        flash('New password must be at least 6 characters long.', 'error')
        return redirect(url_for('settings'))

    # Validate password confirmation
    if new_password != confirm_password:
        flash('New passwords do not match.', 'error')
        return redirect(url_for('settings'))

    # Update password
    current_user.set_password(new_password)
    db.session.commit()

    flash('Your password has been changed successfully!', 'success')
    return redirect(url_for('settings'))


@app.route('/verify_reset_code', methods=['GET', 'POST'])
def verify_reset_code():
    """Verify the password reset code and redirect to password reset if valid"""
    if current_user.is_authenticated:
        return redirect(url_for('course_dashboard'))
    
    # Check if user has an active password reset request
    if 'reset_email' not in session:
        flash('Invalid or expired password reset request. Please try again.', 'danger')
        return redirect(url_for('forgot_password'))
    
    user = User.query.filter_by(email=session['reset_email']).first()
    if not user:
        flash('Invalid or expired password reset request. Please try again.', 'danger')
        session.pop('reset_email', None)
        return redirect(url_for('forgot_password'))
    
    form = VerificationForm()
    
    if form.validate_on_submit():
        code = form.verification_code.data
        
        if user.verify_reset_code(code):
            # Generate a one-time token for the actual password reset
            reset_token = secrets.token_urlsafe(32)
            user.reset_token = reset_token
            user.reset_token_expires = datetime.utcnow() + timedelta(hours=1)
            db.session.commit()
            
            # Store the token in the session for the next step
            session['reset_token'] = reset_token
            return redirect(url_for('reset_password', token=reset_token))
        else:
            flash('Invalid or expired verification code. Please try again.', 'danger')
    
    # For GET requests or failed form validation
    return render_template('verify_code.html', 
                         email=user.email, 
                         verification_type='password_reset',
                         form=form)


@app.route('/forgot_password', methods=['GET', 'POST'])
def forgot_password():
    if current_user.is_authenticated:
        return redirect(url_for('course_dashboard'))
    
    form = ForgotPasswordForm()
    
    if form.validate_on_submit():
        email = form.email.data
        user = User.query.filter_by(email=email).first()
        
        if user:
            # Generate a 6-digit verification code
            reset_code = user.generate_password_reset_code()
            db.session.commit()
            
            # Send password reset email with verification code
            if send_password_reset_email(user, reset_code):
                # Store user email in session for verification
                session['reset_email'] = user.email
                flash('We\'ve sent a 6-digit verification code to your email. Please check your inbox.', 'info')
                return redirect(url_for('verify_reset_code'))
            else:
                flash('Failed to send verification code. Please try again.', 'danger')
        else:
            # Don't reveal that the email doesn't exist for security reasons
            flash('If an account exists with this email, you will receive a verification code.', 'info')
            return redirect(url_for('login'))
            
    return render_template('forgot_password.html', form=form)


@app.route('/reset_password/<token>', methods=['GET', 'POST'])
def reset_password(token):
    if current_user.is_authenticated:
        return redirect(url_for('course_dashboard'))
    
    # Check if the token in the URL matches the one in the session
    if 'reset_token' not in session or session['reset_token'] != token:
        flash('Invalid or expired password reset request. Please try again.', 'danger')
        session.pop('reset_token', None)
        session.pop('reset_email', None)
        return redirect(url_for('forgot_password'))
    
    # Get the user and verify the token is still valid
    user = User.query.filter_by(reset_token=token).first()
    if not user or user.reset_token_expires < datetime.utcnow():
        flash('The password reset link is invalid or has expired.', 'danger')
        session.pop('reset_token', None)
        session.pop('reset_email', None)
        return redirect(url_for('forgot_password'))
    
    # Initialize the form
    form = ResetPasswordForm()
    
    if form.validate_on_submit():
        try:
            # Update password and clear reset token
            user.set_password(form.password.data)
            user.reset_token = None
            user.reset_token_expires = None
            db.session.commit()
            
            # Clear the session
            session.pop('reset_token', None)
            session.pop('reset_email', None)
            
            flash('Your password has been reset successfully! You can now log in with your new password.', 'success')
            return redirect(url_for('login'))
        except Exception as e:
            db.session.rollback()
            flash('An error occurred while resetting your password. Please try again.', 'danger')
            app.logger.error(f'Error resetting password: {str(e)}')
    
    # Generate CSRF token for the form
    csrf_token = generate_csrf()
    return render_template('reset_password.html', form=form, token=token, csrf_token=csrf_token)


# --- File Upload Routes ---
@app.route('/upload_course', methods=['POST'])
@login_required
def upload_course():
    """Handle PDF file upload and create course from content."""
    if 'file' not in request.files:
        flash('No file selected', 'danger')
        return redirect(url_for('home'))
    
    file = request.files['file']
    if file.filename == '':
        flash('No file selected', 'danger')
        return redirect(url_for('home'))
    
    try:
        # Create course from uploaded file
        new_course, error = create_course_from_file_service(file, current_user)
        
        if error:
            flash(f'Error creating course: {error}', 'danger')
            return redirect(url_for('home'))
        
        flash(f'Course "{new_course.course_title}" created successfully from uploaded file!', 'success')
        return redirect(url_for('show_course', course_id=new_course.id))
        
    except Exception as e:
        flash(f'Error processing file: {str(e)}', 'danger')
        return redirect(url_for('home'))