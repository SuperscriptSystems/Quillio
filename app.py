from flask import Flask, render_template, request, session, redirect, url_for, jsonify
from flask_session import Session
from models.test_generator import TestGenerator
from models.answer_checker import AnswerChecker
from models.ask_ai import ask_ai, generate_image_from_prompt
from models.fulltest import Test
from models.question import Question
from models.json_extractor import JsonExtractor
from models.prompt_builders import TestPromptBuilder, CoursePromptBuilder, LessonPromptBuilder
import markdown
import re
import tempfile

app = Flask(__name__)
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
app.config["SESSION_FILE_DIR"] = tempfile.mkdtemp()
Session(app)

test_creator = TestGenerator(ask_ai)
answer_evaluator = AnswerChecker(ask_ai)

def insert_images_from_prompts(text):
    prompt_pattern = r'\[IMAGE_PROMPT:\s*"(.*?)"\]'

    def replace(match):
        prompt = match.group(1)
        try:
            image_url = generate_image_from_prompt(prompt)
            if image_url:
                return f'![{prompt}]({image_url})'
            return f'*[Image generation failed: "{prompt}"]*'
        except Exception:
            return f'*[Image generation error: "{prompt}"]*'

    return re.sub(prompt_pattern, replace, text)


def get_form_inputs():
    return {
        'answer': request.form.get('answer'),
        'question': request.form.get('question'),
        'topic': request.form.get('topic'),
        'knowledge': request.form.get('knowledge'),
        'format': request.form.get('format'),
    }


def render_answer_input(question, format_type):
    if format_type == "free_form":
        return '<textarea name="answer" required placeholder="Type your answer here..."></textarea>'

    if format_type == "multiple_choice":
        html = ""
        for option in question.options.values():
            html += f'<label><input type="radio" name="answer" value="{option}" required> <span>{option}</span></label><br>'
        return html


def generate_test(topic, format_type, prompt):
    if format_type == "free_form":
        return test_creator.generate_open_test(topic, prompt)
    if format_type == "multiple_choice":
        return test_creator.generate_multiple_choice_test(topic, prompt)


def save_test_to_dict(test):
    questions = []
    for q in test.questions:
        questions.append({
            "test_id": q.test_id,
            "question": q.question,
            "options": q.options
        })

    return {
        "test_name": test.test_name,
        "topic": test.topic,
        "questions": questions
    }



def load_test_from_dict(data):
    questions = []
    for q in data["questions"]:
        questions.append(Question(q["test_id"], q["question"], q["options"]))
    return Test(data["test_name"], data["topic"], questions)


def score_summary(test):
    prompt = "Based on these answers and evaluations, give a final score from 0-100:\n\n"

    i = 1
    for test_page in test:
        prompt += f"Q{i}: {test_page['question']}\nA{i}: {test_page['answer']}\nAssessment: {test_page['assessment']}\n\n"
        i += 1

    prompt += "Return just the number."

    result = ask_ai(prompt)
    return int(''.join(filter(str.isdigit, result)))



def prepare_prompt(test, answers):
    questions = []
    user_answers = []
    options = []

    for question in test.questions:
        questions.append(question.question)
        opt_text = ""
        if question.options:
            opt_text = "\nOptions: " + ", ".join(question.options.values())
        options.append(opt_text)

    for answer in answers:
        user_answers.append(answer['answer'])

    prompt = "Evaluate these answers. Format:\nAssessment1: ...\n\n"
    for i in range(len(answers)):
        question_number = i + 1
        question = questions[i]
        option = options[i]
        user_answer = user_answers[i]

        prompt += f"Q{question_number}: {question}{option}\n"
        prompt += f"A{question_number}: {user_answer}\n\n"

    return prompt


def extract_assessments(result, num_answers):
    assessments = []
    for i in range(num_answers):
        key = f"Assessment{i + 1}:"
        next_key = f"Assessment{i + 2}:"
        start = result.find(key)
        end = result.find(next_key) if i + 1 < num_answers else len(result)
        if start != -1:
            text = result[start + len(key):end].strip()
        else:
            text = "No assessment"
        assessments.append(text)
    return assessments


def combine_details(test, answers, assessments):
    detailed = []
    for i in range(len(answers)):
        detailed.append({
            "question": test.questions[i].question,
            "answer": answers[i]['answer'],
            "assessment": assessments[i]
        })
    return detailed


@app.route('/')
def home():
    session.clear()
    return render_template('index.html')


@app.route('/assessment', methods=['GET', 'POST'])
def assessment():
    # If no test in session, redirect to home on GET
    if not session.get('test'):
        if request.method == 'GET':
            return redirect(url_for('index'))

        # On POST, if no test yet, generate and store it
        form = get_form_inputs()
        test = generate_test(form['topic'], form['format'], f"He claims to be {form['knowledge']}/100")
        session['test'] = save_test_to_dict(test)
        session['answers'] = []
        session['index'] = 0
        session['format'] = form['format']
        return redirect(url_for('test_ready'))

    test = load_test_from_dict(session['test'])
    index = session['index']

    # If POST, save the submitted answer
    if request.method == 'POST':
        answer = request.form.get('answer')
        session['answers'].append({
            "question": test.questions[index].question,
            "answer": answer
        })
        session['index'] += 1
        if session['index'] < len(test.questions):
            return redirect(url_for('assessment'))
        return redirect(url_for('loading', context='results'))

    # GET: show the current question
    if index >= len(test.questions):
        return redirect(url_for('loading', context='results'))

    question = test.questions[index]
    input_html = render_answer_input(question, session['format'])
    return render_template(
        'question_page.html',
        test_page=question,
        input_html=input_html,
        current=index + 1,
        total=len(test.questions),
        form_action=url_for('assessment')
    )

def prepare_unit_test_prompt(test_info, user_answers):
    prompt = "Evaluate these answers. Format:\nAssessment1: ...\n\n"
    for i in range(len(user_answers)):
        question = test_info.questions[i]
        answer = user_answers[i]

        options_text = ""
        if question.options:
            options_text = ", ".join(question.options.values())

        prompt += f"Q{i + 1}: {question.question}\n"
        if options_text:
            prompt += f"Options: {options_text}\n"
        prompt += f"A{i + 1}: {answer['answer']}\n\n"
    return prompt


def extract_assessments_from_ai_response(ai_response, num_answers):
    assessments = []
    for i in range(num_answers):
        start_text = f"Assessment{i + 1}:"
        next_text = f"Assessment{i + 2}:"
        start_index = ai_response.find(start_text)
        if i + 1 < num_answers:
            end_index = ai_response.find(next_text)
        else:
            end_index = len(ai_response)

        if start_index != -1:
            assessment = ai_response[start_index + len(start_text):end_index].strip()
        else:
            assessment = "No assessment"
        assessments.append(assessment)
    return assessments


def combine_unit_test_details(user_answers, assessments):
    detailed_results = []
    for i in range(len(user_answers)):
        detailed_results.append({
            "question": user_answers[i]['question'],
            "answer": user_answers[i]['answer'],
            "assessment": assessments[i]
        })
    return detailed_results



@app.route('/test_ready')
def test_ready():
    if not session.get('test'):
        return redirect(url_for('index'))
    return render_template('test_ready.html')


@app.route('/loading/<context>')
def loading(context):
    if context == 'results':
        return render_template('loading.html', message="Analyzing your answers and generating your personalized course...", fetch_url=url_for('get_results_data'))


@app.route('/loading/lesson/<unit_title>/<lesson_title>')
def loading_lesson(unit_title, lesson_title):
    msg = f"Generating {lesson_title}..."
    return render_template('loading.html', message=msg, fetch_url=url_for('get_lesson_data', unit_title=unit_title, lesson_title=lesson_title))

@app.route('/get_results_data')
def get_results_data():
    answers = session.get('answers', [])
    test_dict = session.get('test')

    if not answers or not test_dict:
        raise Exception("Missing test data")

    test = load_test_from_dict(test_dict)
    prompt = prepare_prompt(test, answers)

    result = ask_ai(prompt)
    assessments = extract_assessments(result, len(answers))
    detailed = combine_details(test, answers, assessments)

    session['assessed_answers'] = detailed

    score = score_summary(detailed)
    session['final_score'] = score

    course_prompt = CoursePromptBuilder.build_course_structure_prompt(test.topic, score, detailed)
    raw_course = ask_ai(course_prompt)
    course = JsonExtractor.extract_json(raw_course)
    session['course_structure'] = course

    return jsonify({'redirect_url': url_for('show_results')})




@app.route('/results')
def show_results():
    if not session.get('assessed_answers'):
        return redirect(url_for('index'))
    return render_template('results.html', answers=session['assessed_answers'], final_score=session.get('final_score'))


@app.route('/course')
def show_course():
    if not session.get('course_structure'):
        return redirect(url_for('index'))
    return render_template('course.html', course=session['course_structure'])


@app.route('/get_lesson_data/<unit_title>/<lesson_title>')
def get_lesson_data(unit_title, lesson_title):
    prompt = LessonPromptBuilder.build_lesson_content_prompt(lesson_title, unit_title)
    markdown_text = ask_ai(prompt)
    markdown_text = insert_images_from_prompts(markdown_text)
    html = markdown.markdown(markdown_text, extensions=["fenced_code", "tables"])
    session['current_lesson'] = {'title': lesson_title, 'content': html}
    return jsonify({'redirect_url': url_for('show_lesson')})


@app.route('/lesson')
def show_lesson():
    lesson = session.get('current_lesson')
    if not lesson:
        return redirect(url_for('show_course'))
    return render_template('lesson_page.html', title=lesson['title'], content=lesson['content'])



@app.route('/start_unit_test/<unit_title>/<test_title>')
def start_unit_test(unit_title, test_title):
    topic = f"{unit_title}: {test_title}"
    test = test_creator.generate_multiple_choice_test(topic, "Create 5-10 questions.")
    session['current_unit_test'] = save_test_to_dict(test)
    session['current_unit_test_index'] = 0
    session['current_unit_test_answers'] = []
    session['current_unit_test_format'] = 'multiple_choice'
    return redirect(url_for('unit_test'))


@app.route('/unit_test', methods=['GET', 'POST'])
def unit_test():
    if 'current_unit_test' not in session:
        return redirect(url_for('show_course'))
    test = load_test_from_dict(session['current_unit_test'])
    test_index = session['current_unit_test_index']
    if request.method == 'POST':
        answer = request.form.get('answer')
        session['current_unit_test_answers'].append({"question": test.questions[test_index].question, "answer": answer})
        session['current_unit_test_index'] += 1
        if session['current_unit_test_index'] < len(test.questions):
            return redirect(url_for('unit_test'))
        return redirect(url_for('unit_test_results'))
    if test_index >= len(test.questions):
        return redirect(url_for('unit_test_results'))
    page = test.questions[test_index]
    input_html = render_answer_input(page, session['current_unit_test_format'])
    return render_template('question_page.html', test_page=page, input_html=input_html, current=test_index + 1,
                           total=len(test.questions), form_action=url_for('unit_test'))



@app.route('/unit_test_results')
def unit_test_results():
    if 'current_unit_test' not in session:
        return redirect(url_for('show_course'))

    test_info = load_test_from_dict(session['current_unit_test'])
    user_answers = session['current_unit_test_answers']

    prompt = prepare_unit_test_prompt(test_info, user_answers)
    ai_response = ask_ai(prompt)

    assessments = extract_assessments_from_ai_response(ai_response, len(user_answers))
    detailed_results = combine_unit_test_details(user_answers, assessments)

    final_score = score_summary(detailed_results)

    keys_to_remove = [
        'current_unit_test', 'current_unit_test_index',
        'current_unit_test_answers', 'current_unit_test_format'
    ]
    for key in keys_to_remove:
        session.pop(key, None)

    return render_template(
        'unit_test_results.html',
        answers=detailed_results,
        final_score=final_score,
        test_name=test_info.test_name
    )




if __name__ == '__main__':
    app.run(debug=True)
