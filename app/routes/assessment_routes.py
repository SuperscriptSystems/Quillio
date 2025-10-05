from flask import Blueprint, render_template, session, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from app.forms import InitialAssessmentForm, AnswerForm
from app.helpers import save_test_to_dict, load_test_from_dict, render_answer_input
from app.services import (
    generate_test_service,
    evaluate_answers_service,
    generate_knowledge_assessment_service,
    calculate_percentage_score_service,
    create_course_service,
)
from app.models import UnitTestResult
from app.configuration import db
import time

assessment_bp = Blueprint('assessment', __name__)


@assessment_bp.route('/assessment', methods=['GET', 'POST'])
@login_required
def assessment():
    if 'test' in session:
        test = load_test_from_dict(session['test'])
        current_index = session.get('index', 0)
        if current_index >= len(test.questions):
            return redirect(url_for('loading', context='results'))
        current_question = test.questions[current_index]
        form = AnswerForm()
        form.answer.choices = [(key, value) for key, value in current_question.options.items()]
        if form.validate_on_submit():
            if 'answers' not in session:
                session['answers'] = []
            selected_option = next((text for value, text in form.answer.choices if value == form.answer.data), form.answer.data)
            session['answers'].append({
                'question': current_question.question,
                'answer': selected_option,
                'answer_value': form.answer.data
            })
            session['index'] = current_index + 1
            session.modified = True
            if session['index'] < len(test.questions):
                return redirect(url_for('assessment.assessment'))
            else:
                return redirect(url_for('loading', context='results'))
        return render_template('assessment.html', form=form, test=test, index=current_index)
    form = InitialAssessmentForm()
    if form.validate_on_submit():
        topic = form.topic.data
        knowledge = form.knowledge.data
        additional_context = f"User claims to be {knowledge}/100 in their knowledge of the topic."
        user_profile = {'age': current_user.age, 'bio': current_user.bio}
        test = generate_test_service(topic, "multiple_choice", additional_context, current_user.language, user_profile=user_profile)
        if not test:
            flash("There was an error generating the test. Please try again.", "danger")
            return redirect(url_for('course.home'))
        session['test'] = save_test_to_dict(test)
        session['answers'] = []
        session['index'] = 0
        return redirect(url_for('assessment.assessment'))
    return render_template('assessment.html', form=form)


@assessment_bp.route('/test_ready')
@login_required
def test_ready():
    if 'test' not in session:
        return redirect(url_for('course.home'))
    return render_template('test_ready.html', lang=current_user.language)


@assessment_bp.route('/results')
@login_required
def show_results():
    if 'assessed_answers' not in session:
        return redirect(url_for('course.home'))
    return render_template('results.html', answers=session['assessed_answers'], knowledge_assessment=session.get('knowledge_assessment'), course_id=session.get('current_course_id'), lang=current_user.language)


@assessment_bp.route('/loading/<context>')
@login_required
def loading(context):
    lang = current_user.language
    message = ''
    fetch_url = ''
    if context == 'results':
        message = "Анализируем ваши ответы и создаем персональный курс..." if lang == 'russian' else "Analyzing your answers and generating your personalized course..."
        fetch_url = url_for('assessment.get_results_data')
    elif context == 'unit_results':
        message = "Анализируем ваши ответы..." if lang == 'russian' else "Analyzing your answers..."
        fetch_url = url_for('assessment.get_unit_results_data')
    else:
        return redirect(url_for('course.home'))
    return render_template('loading.html', message=message, fetch_url=fetch_url, lang=lang)


@assessment_bp.route('/get_results_data')
@login_required
def get_results_data():
    test = load_test_from_dict(session['test'])
    detailed_results = evaluate_answers_service(test.questions, session['answers'], current_user.language)
    if not detailed_results:
        flash("There was an error evaluating your test answers. Please try again.", "danger")
        for key in ['test', 'answers', 'index']:
            session.pop(key, None)
        return jsonify({'redirect_url': url_for('course.home')})
    knowledge_assessment = generate_knowledge_assessment_service(detailed_results)
    if "Error:" in knowledge_assessment or "Unauthorized" in knowledge_assessment:
        flash("Your test was graded, but we could not generate a course. The API key is invalid or your account has billing issues. Please check your credentials.", "danger")
        session['assessed_answers'] = detailed_results
        session['knowledge_assessment'] = "Could not be generated due to an API authentication error."
        for key in ['test', 'answers', 'index', 'current_course_id']:
            session.pop(key, None)
        return jsonify({'redirect_url': url_for('assessment.show_results')})
    new_course = create_course_service(current_user, test.topic, knowledge_assessment, detailed_results)
    if not new_course:
        flash("We're sorry, but we couldn't create your course at this time. Please try again later.", "danger")
        return jsonify({'redirect_url': url_for('course.home')})
    session['assessed_answers'] = detailed_results
    session['knowledge_assessment'] = knowledge_assessment
    session['current_course_id'] = new_course.id
    for key in ['test', 'answers', 'index']:
        session.pop(key, None)
    return jsonify({'redirect_url': url_for('assessment.show_results')})


@assessment_bp.route('/loading/unit_test/<uuid:course_id>/<unit_title>/<test_title>')
@login_required
def loading_unit_test(course_id, unit_title, test_title):
    course = Course.query.get_or_404(course_id)
    if course.user_id != current_user.id:
        flash("You do not have permission to start this test.", "danger")
        return redirect(url_for('course.course_dashboard'))
    lang = current_user.language
    message = f"Готовим ваш тест для {unit_title}..." if lang == 'russian' else f"Preparing your test for {unit_title}..."
    fetch_url = url_for('assessment.get_unit_test_data', course_id=course_id, unit_title=unit_title, test_title=test_title)
    return render_template('loading.html', message=message, fetch_url=fetch_url, lang=lang)


@assessment_bp.route('/get_unit_test_data/<uuid:course_id>/<unit_title>/<test_title>')
@login_required
def get_unit_test_data(course_id, unit_title, test_title):
    course = Course.query.get_or_404(course_id)
    if course.user_id != current_user.id:
        return jsonify({"error": "Unauthorized"}), 403
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
        return jsonify({'redirect_url': url_for('course.show_course', course_id=course_id)})
    lesson_content_context = "\n\n".join([lesson.html_content for lesson in lessons_in_unit if lesson.html_content])
    topic = f"{unit_title}: {test_title}"
    user_profile = {'age': current_user.age, 'bio': current_user.bio}
    test = generate_test_service(topic, "multiple_choice", "Create 5-10 questions.", current_user.language, user_profile=user_profile, lesson_content_context=lesson_content_context)
    if not test:
        flash(f"Could not generate the test for {unit_title}. There may have been an issue with the AI service.", "danger")
        return jsonify({'redirect_url': url_for('course.show_course', course_id=course_id)})
    session['current_unit_test'] = save_test_to_dict(test)
    session['current_unit_test_index'] = 0
    session['current_unit_test_answers'] = []
    session['current_course_id'] = course_id
    session['current_unit_title'] = unit_title
    session.modified = True
    return jsonify({'redirect_url': url_for('assessment.unit_test')})


@assessment_bp.route('/unit_test', methods=['GET', 'POST'])
@login_required
def unit_test():
    try:
        if 'current_unit_test' not in session:
            return redirect(url_for('course.course_dashboard'))
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
                        return redirect(url_for('assessment.loading', context='unit_results'))
                    return redirect(url_for('assessment.unit_test'))
            flash('Please select an answer before continuing.', 'error')
            return render_question(test, test_index, current_user.language)
        if test_index >= len(test.questions):
            return redirect(url_for('assessment.loading', context='unit_results'))
        return render_question(test, test_index, current_user.language)
    except Exception:
        flash('An error occurred while loading the test. Please try again.', 'error')
        return redirect(url_for('course.course_dashboard'))


def render_question(test, test_index, lang):
    current_question = test.questions[test_index]
    form = AnswerForm()
    if hasattr(current_question, 'choices'):
        form.answer.choices = [(str(i), str(choice)) for i, choice in enumerate(current_question.choices)]
    input_html = render_answer_input(current_question)
    return render_template('question_page.html', test_page=current_question, input_html=input_html, current=test_index + 1, total=len(test.questions), form=form, lang=lang)


@assessment_bp.route('/get_unit_results_data')
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
        existing_result = UnitTestResult.query.filter_by(user_id=current_user.id, course_id=course_id, unit_title=unit_title).first()
        if existing_result:
            existing_result.score = final_score
        else:
            new_result = UnitTestResult(user_id=current_user.id, course_id=course_id, unit_title=unit_title, score=final_score)
            db.session.add(new_result)
        db.session.commit()
    session['unit_test_final_results'] = {'answers': detailed_results, 'final_score': final_score, 'test_name': test_info.test_name, 'course_id': course_id}
    for key in ['current_unit_test', 'current_unit_test_index', 'current_unit_test_answers', 'current_course_id', 'current_unit_title']:
        session.pop(key, None)
    return jsonify({'redirect_url': url_for('assessment.show_unit_test_results')})


@assessment_bp.route('/unit_test_results')
@login_required
def show_unit_test_results():
    if 'unit_test_final_results' not in session:
        return redirect(url_for('course.course_dashboard'))
    results = session.pop('unit_test_final_results', None)
    if not results:
        return redirect(url_for('course.course_dashboard'))
    return render_template('unit_test_results.html', answers=results['answers'], final_score=results['final_score'], test_name=results['test_name'], course_id=results['course_id'])

