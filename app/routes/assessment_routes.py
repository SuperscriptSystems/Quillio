from flask import Blueprint, render_template, session, redirect, url_for, flash, jsonify, request
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
from app.models import UnitTestResult, Course, Lesson
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
            return redirect(url_for('assessment.loading', context='results'))
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
                return redirect(url_for('assessment.loading', context='results'))
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
    
    return jsonify({'redirect_url': url_for('assessment.unit_test')})


@assessment_bp.route('/unit_test', methods=['GET', 'POST'])
@login_required
def unit_test():
    try:
        # Check if test exists in session
        if 'current_unit_test' not in session:
            flash('No test found. Please try again.', 'error')
            return redirect(url_for('course.course_dashboard'))
            
        # Load test data
        test = load_test_from_dict(session['current_unit_test'])
        
        # Initialize session variables if they don't exist
        if 'current_unit_test_index' not in session:
            session['current_unit_test_index'] = 0
        if 'current_unit_test_answers' not in session:
            session['current_unit_test_answers'] = []
            
        current_index = session['current_unit_test_index']
        
        # Check if we've completed all questions
        if current_index >= len(test.questions):
            return redirect(url_for('assessment.get_unit_results_data'))
        
        # Handle form submission
        if request.method == 'POST':
            form = AnswerForm()
            
            # Get current question
            current_question = test.questions[current_index]
            
            # Set up form choices if options are available
            if hasattr(current_question, 'options') and current_question.options:
                form.answer.choices = [(key, value) for key, value in current_question.options.items()]
            
            if form.validate_on_submit() or 'answer' in request.form:
                # Get the answer from form or direct request
                answer_data = {
                    'question': current_question.question,
                    'answer_value': request.form.get('answer', ''),
                    'answer': '',  # Will be set based on choices if available
                    'correct_answer': getattr(current_question, 'correct_answer', '')
                }
                
                # If this is a multiple choice question, get the actual answer text
                if hasattr(current_question, 'options') and current_question.options:
                    try:
                        choice_index = int(answer_data['answer_value'])
                        answer_data['answer'] = current_question.options.get(str(choice_index), answer_data['answer_value'])
                    except (ValueError, KeyError):
                        answer_data['answer'] = answer_data['answer_value']
                else:
                    answer_data['answer'] = answer_data['answer_value']
                
                # Save the answer
                session['current_unit_test_answers'].append(answer_data)
                session.modified = True
                
                # Move to next question or finish test
                session['current_unit_test_index'] += 1
                
                if session['current_unit_test_index'] >= len(test.questions):
                    return redirect(url_for('assessment.get_unit_results_data'))
                    
                return redirect(url_for('assessment.unit_test'))
            else:
                flash('Please select an answer before continuing.', 'error')
        
        # Handle GET request - show current question
        current_question = test.questions[current_index]
        form = AnswerForm()
        
        # Set up form choices if options are available
        if hasattr(current_question, 'options') and current_question.options:
            form.answer.choices = [(key, value) for key, value in current_question.options.items()]
        
        return render_template('unit_test.html',
                            form=form,
                            question=current_question,
                            current=current_index + 1,
                            total=len(test.questions),
                            lang=current_user.language)
                            
    except Exception as e:
        print(f"Error in unit_test: {str(e)}")
        flash('An error occurred while loading the test. Please try again.', 'error')
        return redirect(url_for('course.course_dashboard'))


def render_question(test, test_index, lang):
    current_question = test.questions[test_index]
    form = AnswerForm()
    
    # Handle different question types and attributes
    if hasattr(current_question, 'choices'):
        form.answer.choices = [(str(i), str(choice)) for i, choice in enumerate(current_question.choices)]
    elif hasattr(current_question, 'options'):
        # Handle questions with 'options' attribute
        form.answer.choices = [(str(i), str(option)) for i, option in enumerate(current_question.options.values())]
    
    try:
        input_html = render_answer_input(current_question)
    except Exception as e:
        print(f"Error in render_answer_input: {str(e)}")
        # Fallback to a simple input if rendering fails
        input_html = '<input type="text" name="answer" required>'
    
    return render_template('question_page.html', 
                         test_page=current_question, 
                         input_html=input_html, 
                         current=test_index + 1, 
                         total=len(test.questions), 
                         form=form, 
                         lang=lang)


@assessment_bp.route('/get_unit_results_data')
@login_required
def get_unit_results_data():
    try:
        if 'current_unit_test' not in session:
            flash('No test in progress. Please start a new test.', 'error')
            return redirect(url_for('course.course_dashboard'))
            
        # Load test data
        test_info = load_test_from_dict(session['current_unit_test'])
        user_answers = session.get('current_unit_test_answers', [])
        course_id = session.get('current_course_id')
        unit_title = session.get('current_unit_title')
        
        # Ensure we have answers to evaluate
        if not user_answers:
            flash('No answers found for this test. Please try again.', 'error')
            return redirect(url_for('course.course_dashboard'))
        
        # Evaluate answers
        detailed_results = evaluate_answers_service(test_info.questions, user_answers, current_user.language)
        
        # Process and validate results
        processed_answers = []
        correct_answers = 0
        
        for i, answer in enumerate(detailed_results, 1):
            # Ensure all required fields exist
            processed = {
                'question': answer.get('question', f'Question {i}'),
                'answer': answer.get('answer', ''),
                'answer_value': str(answer.get('answer_value', '')),
                'correct_answer': str(answer.get('correct_answer', '')),
                'assessment': answer.get('assessment', '')
            }
            
            # Determine if answer is correct by checking the assessment text
            assessment = str(answer.get('assessment', '')).lower()
            
            # Check for clear indicators of correct/incorrect in the assessment text
            is_correct = False
            
            # Check for positive indicators
            if any(word in assessment for word in ['correct', 'right', 'верно', 'правильно', 'accurate', 'true', 'yes']):
                is_correct = True
            
            # Override if there are negative indicators
            if any(word in assessment for word in ['incorrect', 'wrong', 'неверно', 'неправильно', 'inaccurate', 'false', 'no']):
                is_correct = False
                
            # Special case: if assessment starts with 'correct' or 'incorrect', use that
            if assessment.startswith('correct'):
                is_correct = True
            elif assessment.startswith('incorrect'):
                is_correct = False
                
            processed['is_correct'] = is_correct
            
            # Count correct answers
            if is_correct:
                correct_answers += 1
                
            processed_answers.append(processed)
        
        # Calculate statistics
        total_questions = len(processed_answers)
        final_score = int((correct_answers / total_questions) * 100) if total_questions > 0 else 0
        
        # Save to database if we have course and unit info
        if course_id and unit_title:
            try:
                existing_result = UnitTestResult.query.filter_by(
                    user_id=current_user.id, 
                    course_id=course_id, 
                    unit_title=unit_title
                ).first()
                
                if existing_result:
                    existing_result.score = final_score
                    existing_result.completed_at = datetime.utcnow()
                else:
                    new_result = UnitTestResult(
                        user_id=current_user.id,
                        course_id=course_id,
                        unit_title=unit_title,
                        score=final_score,
                        completed_at=datetime.utcnow()
                    )
                    db.session.add(new_result)
                db.session.commit()
            except Exception as e:
                print(f"Error saving test result to database: {str(e)}")
                db.session.rollback()
        
        # Prepare final results data
        results_data = {
            'answers': processed_answers,
            'final_score': final_score,
            'test_name': getattr(test_info, 'test_name', 'Unit Test'),
            'course_id': course_id,
            'unit_title': unit_title,
            'total_questions': total_questions,
            'correct_answers': correct_answers
        }
        
        # Store in session
        session['unit_test_final_results'] = results_data
        
        # Clean up session
        cleanup_keys = [
            'current_unit_test',
            'current_unit_test_index',
            'current_unit_test_answers',
            'current_course_id',
            'current_unit_title'
        ]
        for key in cleanup_keys:
            session.pop(key, None)
            
        # Redirect to show results page directly (no JSON response needed)
        return redirect(url_for('assessment.show_unit_test_results'))
        
    except Exception as e:
        print(f"Error in get_unit_results_data: {str(e)}")
        flash('An error occurred while processing your test results. Please try again.', 'error')
        return redirect(url_for('course.course_dashboard'))


@assessment_bp.route('/unit_test_results')
@login_required
def show_unit_test_results():
    # Get results from session
    results = session.get('unit_test_final_results')
    
    # If no results in session, show error
    if not results:
        flash('No test results found. Please try taking the test again.', 'error')
        return redirect(url_for('course.course_dashboard'))
    
    # Ensure we have answers to display
    answers = results.get('answers', [])
    if not answers:
        flash('No answers found in test results. Please try again.', 'error')
        return redirect(url_for('course.course_dashboard'))
    
    # Process each answer to ensure all required fields are present
    processed_answers = []
    for i, answer in enumerate(answers, 1):
        # Ensure all required fields exist with defaults
        processed = {
            'question': answer.get('question', f'Question {i}'),
            'answer': str(answer.get('answer', '')),
            'answer_value': str(answer.get('answer_value', '')),
            'correct_answer': str(answer.get('correct_answer', '')),
            'assessment': str(answer.get('assessment', '')),
            'is_correct': bool(answer.get('is_correct', False))
        }
        
        # If is_correct wasn't set, try to determine it from assessment text
        if not processed['is_correct'] and processed['assessment']:
            assessment = processed['assessment'].lower()
            processed['is_correct'] = any(word in assessment 
                                       for word in ['correct', 'right', 'верно', 'правильно'])
        
        processed_answers.append(processed)
    
    # Calculate statistics
    total_questions = len(processed_answers)
    correct_answers = sum(1 for a in processed_answers if a['is_correct'])
    
    # Use provided score or calculate it
    final_score = results.get('final_score')
    if final_score is None:
        final_score = int((correct_answers / total_questions) * 100) if total_questions > 0 else 0
    
    # Prepare template context
    context = {
        'answers': processed_answers,
        'final_score': final_score,  # Changed from 'score' to 'final_score' to match template
        'total_questions': total_questions,
        'correct_answers': correct_answers,
        'test_name': results.get('test_name', 'Unit Test'),
        'unit_title': results.get('unit_title', ''),
        'course_id': results.get('course_id'),
        'lang': current_user.language
    }
    
    # Clear the results from session to prevent showing them again on refresh
    if 'unit_test_final_results' in session:
        session.pop('unit_test_final_results')
    
    return render_template('unit_test_results.html', **context)
