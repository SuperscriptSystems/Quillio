from flask import render_template, request, session, redirect, url_for, jsonify, flash, Response, stream_with_context
from flask_login import login_user, logout_user, login_required, current_user
import time
import datetime
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


# --- Authentication and Main Navigation Routes ---
@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('course_dashboard'))
    if request.method == 'POST':
        user = User.query.filter_by(username=request.form.get('username')).first()
        if user and user.check_password(request.form.get('password')):
            login_user(user)
            return redirect(url_for('course_dashboard'))
        else:
            flash('Invalid username or password. Please try again.', 'danger')
    return render_template('login.html')


@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('course_dashboard'))
    if request.method == 'POST':
        username, password = request.form.get('username'), request.form.get('password')
        if User.query.filter_by(username=username).first():
            flash('Username already exists.', 'warning')
            return redirect(url_for('register'))
        new_user = User(username=username)
        new_user.set_password(password)
        db.session.add(new_user)
        db.session.commit()
        flash('Registration successful! Please log in.', 'success')
        return redirect(url_for('login'))
    return render_template('register.html')


@app.route('/health', methods=['GET'])
def healthcheck():
    return "OK", 200


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
                           user_name=current_user.username,
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
            test = generate_test_service(topic, "multiple_choice", f"User claims to be {knowledge}/100",
                                         current_user.language)
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
    if 'assessed_answers' not in session: return redirect(url_for('home'))
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
    if not lesson or lesson.course.user_id != current_user.id:
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

    topic = f"{unit_title}: {test_title}"
    test = generate_test_service(topic, "multiple_choice", "Create 5-10 questions.", current_user.language)
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