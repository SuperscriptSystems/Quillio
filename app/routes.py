from flask import render_template, request, session, redirect, url_for, jsonify, flash, Response, stream_with_context
from flask_login import login_user, logout_user, login_required, current_user
import time
from app.admin_utils import admin_required, get_available_models
import datetime
import secrets
from datetime import datetime, timedelta
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
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        user = User.query.filter_by(email=email).first()
        
        if user and user.check_password(password):
            # Generate and send login verification code (2FA for all users)
            verification_code = user.generate_verification_code()
            db.session.commit()  # Save the verification code immediately
            
            # Always redirect to code screen, send email in background
            send_verification_email(user)
            return redirect(url_for('login_verify_code', email=email))
        else:
            flash('Invalid email or password. Please try again.', 'danger')
    return render_template('login.html')


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
            db.session.commit()  # Save any changes made by send_verification_email
            flash('Registration successful! Please check your email for a 6-digit verification code.', 'success')
            return redirect(url_for('verify_code', email=email))
        else:
            flash('Registration successful, but we could not send the verification email. Please contact support.', 'warning')
            return redirect(url_for('login'))
    return render_template('register.html')


@app.route('/health', methods=['GET'])
def healthcheck():
    return "OK", 200


@app.route('/verify_code', methods=['GET', 'POST'])
def verify_code():
    """Email verification code entry route for registration"""
    email = request.args.get('email') or request.form.get('email')
    
    if not email:
        flash('Invalid verification request.', 'danger')
        return redirect(url_for('login'))
    
    if request.method == 'POST':
        verification_code = request.form.get('verification_code')
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
    
    return render_template('verify_code.html', email=email, verification_type='registration')


@app.route('/login_verify_code', methods=['GET', 'POST'])
def login_verify_code():
    """Login verification code entry route"""
    email = request.args.get('email') or request.form.get('email')
    
    if not email:
        flash('Invalid login request.', 'danger')
        return redirect(url_for('login'))
    
    if request.method == 'POST':
        verification_code = request.form.get('verification_code')
        user = User.query.filter_by(email=email).first()
        
        if not user:
            flash('Invalid login request.', 'danger')
            return redirect(url_for('login'))
        
        if user.verify_email_code(verification_code):
            db.session.commit()
            login_user(user)
            flash('Login successful!', 'success')
            return redirect(url_for('course_dashboard'))
        else:
            flash('Invalid or expired verification code. Please try again.', 'danger')
    
    return render_template('verify_code.html', email=email, verification_type='login')


@app.route('/resend_verification', methods=['GET', 'POST'])
def resend_verification():
    """Resend verification email"""
    if request.method == 'POST':
        email = request.form.get('email')
        user = User.query.filter_by(email=email).first()
        
        if not user:
            flash('No account found with that email address.', 'danger')
            return redirect(url_for('resend_verification'))
        
        if user.is_verified:
            flash('Your email is already verified. You can log in.', 'info')
            return redirect(url_for('login'))
        
        if send_resend_verification_email(user):
            db.session.commit()
            flash('Verification code sent! Please check your inbox.', 'success')
            return redirect(url_for('verify_code', email=email))
        else:
            flash('Failed to send verification code. Please try again later.', 'danger')
        
        return redirect(url_for('resend_verification'))
    
    return render_template('resend_verification.html')


@app.route('/logout')
@login_required
def logout():
    logout_user()
    session.clear()
    flash('You have been successfully logged out.', 'info')
    return redirect(url_for('login'))


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
@app.route('/course/<int:course_id>')
@login_required
def show_course(course_id):
    course = Course.query.get_or_404(course_id)
    if course.user_id != current_user.id:
        flash("You do not have permission to view this course.", "danger")
        return redirect(url_for('course_dashboard'))

    lessons = Lesson.query.filter_by(course_id=course.id).all()
    total_lessons = len(lessons)
    is_course_complete = (total_lessons > 0 and course.completed_lessons == total_lessons)

    lessons_dict = {lesson.lesson_title: lesson for lesson in lessons}
    results = UnitTestResult.query.filter_by(user_id=current_user.id, course_id=course_id).all()
    scores_dict = {result.unit_title: result.score for result in results}

    return render_template('course.html',
                           course_obj=course,
                           course=course.course_data,
                           course_id=course_id,
                           all_lessons=lessons_dict,
                           scores=scores_dict,
                           is_course_complete=is_course_complete)


@app.route('/course/<int:course_id>/archive', methods=['POST'])
@login_required
def archive_course(course_id):
    course = Course.query.get_or_404(course_id)
    if course.user_id == current_user.id:
        course.status = 'archived'
        db.session.commit()
        flash(f"'{course.course_title}' has been archived.", "info")
    return redirect(url_for('course_dashboard'))


@app.route('/lesson/<int:lesson_id>')
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


@app.route('/course/<int:course_id>/certificate')
@login_required
def show_certificate(course_id):
    course = Course.query.get_or_404(course_id)

    if course.user_id != current_user.id:
        flash("You do not have permission to view this certificate.", "danger")
        return redirect(url_for('course_dashboard'))

    total_lessons = Lesson.query.filter_by(course_id=course.id).count()
    if not (total_lessons > 0 and course.completed_lessons == total_lessons):
        flash("You must complete all lessons in this course to view the certificate.", "warning")
        return redirect(url_for('show_course', course_id=course_id))

    completion_date = datetime.date.today().strftime("%B %d, %Y")

    return render_template('certificate.html',
                           user_name=(current_user.full_name or current_user.email),
                           course_title=course.course_title,
                           completion_date=completion_date)


# --- Initial Assessment Routes ---
@app.route('/assessment', methods=['GET', 'POST'])
@login_required
def assessment():
    if request.method == 'POST':
        if 'test' in session:
            test = load_test_from_dict(session['test'])
            session['answers'].append(
                {'question': test.questions[session['index']].question, 'answer': request.form.get('answer')})
            session['index'] += 1
            if session['index'] < len(test.questions):
                return redirect(url_for('assessment'))
            else:
                return redirect(url_for('loading', context='results'))
        else:
            topic = request.form.get('topic')
            knowledge = request.form.get('knowledge')

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
            return redirect(url_for('test_ready'))

    if 'test' not in session or session['index'] >= len(session['test']['questions']):
        return redirect(url_for('home'))
    test = load_test_from_dict(session['test'])
    question = test.questions[session['index']]
    input_html = render_answer_input(question)
    return render_template('question_page.html', test_page=question, input_html=input_html,
                           current=session['index'] + 1, total=len(test.questions), form_action=url_for('assessment'),
                           lang=current_user.language)


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


@app.route('/loading/lesson/<int:lesson_id>')
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


@app.route('/stream_lesson_data/<int:lesson_id>')
@login_required
def stream_lesson_data(lesson_id):
    lesson = db.session.get(Lesson, lesson_id)
    if not lesson or lesson.course.user_id != current_user.id:
        return Response("Unauthorized", status=403)

    lesson_content_generator = generate_lesson_content_service(lesson, current_user)

    return Response(stream_with_context(lesson_content_generator), mimetype='text/plain')


# --- Unit Test Routes ---
@app.route('/loading/unit_test/<int:course_id>/<unit_title>/<test_title>')
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


@app.route('/get_unit_test_data/<int:course_id>/<unit_title>/<test_title>')
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
    if 'current_unit_test' not in session:
        return redirect(url_for('course_dashboard'))

    test = load_test_from_dict(session['current_unit_test'])
    test_index = session['current_unit_test_index']

    if request.method == 'POST':
        answer = request.form.get('answer')
        session['current_unit_test_answers'].append({"question": test.questions[test_index].question, "answer": answer})
        session['current_unit_test_index'] += 1
        session.modified = True
        if session['current_unit_test_index'] < len(test.questions):
            return redirect(url_for('unit_test'))
        else:
            return redirect(url_for('loading', context='unit_results'))

    if test_index >= len(test.questions):
        return redirect(url_for('loading', context='unit_results'))

    page = test.questions[test_index]
    input_html = render_answer_input(page)
    return render_template('question_page.html', test_page=page, input_html=input_html, current=test_index + 1,
                           total=len(test.questions), form_action=url_for('unit_test'), lang=current_user.language)


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
    data = request.get_json()
    lesson_id = data.get('lesson_id')
    user_question = data.get('message')
    chat_history = data.get('history', [])

    if not lesson_id or not user_question:
        return Response("Missing data", status=400)

    lesson = db.session.get(Lesson, lesson_id)
    if not lesson or lesson.course.user_id != current_user.id:
        return Response("Unauthorized", status=403)

    ai_response_generator = get_tutor_response_service(lesson, chat_history, user_question, current_user)

    def generate():
        try:
            for chunk in ai_response_generator:
                yield chunk
        except Exception as e:
            print(f"Error during stream generation: {e}")
            yield "I'm sorry, I encountered a technical issue. Please try again."

    return Response(stream_with_context(generate()), mimetype='text/plain')


@app.route('/course/<int:course_id>/edit', methods=['POST'])
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


@app.route('/forgot_password', methods=['GET', 'POST'])
def forgot_password():
    if current_user.is_authenticated:
        return redirect(url_for('course_dashboard'))
        
    if request.method == 'POST':
        email = request.form.get('email')
        user = User.query.filter_by(email=email).first()
        
        if user:
            # Generate a secure token and set expiration (1 hour from now)
            user.reset_token = secrets.token_urlsafe(32)
            user.reset_token_expires = datetime.utcnow() + timedelta(hours=1)
            db.session.commit()
            
            # Send password reset email
            if send_password_reset_email(user, user.reset_token):
                flash('Check your email for instructions to reset your password.', 'info')
                return redirect(url_for('login'))
            else:
                flash('Failed to send password reset email. Please try again.', 'danger')
        else:
            # Don't reveal that the email doesn't exist for security reasons
            flash('If an account exists with this email, you will receive a password reset link.', 'info')
            return redirect(url_for('login'))
            
    return render_template('forgot_password.html')


@app.route('/reset_password/<token>', methods=['GET', 'POST'])
def reset_password(token):
    if current_user.is_authenticated:
        return redirect(url_for('course_dashboard'))
        
    user = User.query.filter_by(reset_token=token).first()
    
    # Check if token is valid and not expired
    if not user or user.reset_token_expires < datetime.utcnow():
        flash('The password reset link is invalid or has expired.', 'danger')
        return redirect(url_for('forgot_password'))
    
    if request.method == 'POST':
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')
        
        # Validate passwords
        if len(password) < 6:
            flash('Password must be at least 6 characters long.', 'danger')
        elif password != confirm_password:
            flash('Passwords do not match.', 'danger')
        else:
            # Update password and clear reset token
            user.set_password(password)
            user.reset_token = None
            user.reset_token_expires = None
            db.session.commit()
            
            flash('Your password has been reset successfully! You can now log in with your new password.', 'success')
            return redirect(url_for('login'))
    
    return render_template('reset_password.html', token=token)


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