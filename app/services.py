import requests
import json
import os
import re
import markdown
from models.prompt_builders import TestPromptBuilder, AnswerPromptBuilder, CoursePromptBuilder, LessonPromptBuilder
from models.json_extractor import JsonExtractor
from models.fulltest import Test
from models.question import Question
from models.answer_checker import AnswerChecker
from app.models import db, Course, Lesson

OPENAI_API_KEY = os.environ.get("API_KEY_OPENAI")

# --- AI Interaction Functions ---
def ask_ai(prompt, model="gpt-4.1-mini"):
    headers = {'Content-Type': 'application/json', 'Authorization': f'Bearer {OPENAI_API_KEY}'}
    data = {'model': model, 'messages': [{'role': 'user', 'content': prompt}], 'max_tokens': 3000, 'temperature': 0.7}
    try:
        response = requests.post("https://api.openai.com/v1/chat/completions", headers=headers, data=json.dumps(data))
        response.raise_for_status()
        return response.json()['choices'][0]['message']['content']
    except requests.exceptions.RequestException as e:
        print(f"Error communicating with OpenAI Chat model: {e}")
        return None

# --- Test and Assessment Services ---
def generate_test_service(topic, format_type, additional_context, language):
    if format_type == "multiple_choice":
        prompt = TestPromptBuilder.build_multiple_choice_prompt(topic, additional_context, language)
    else:  # free_form
        prompt = TestPromptBuilder.build_open_question_prompt(topic, additional_context, language)

    raw_output = ask_ai(prompt)
    if not raw_output:
        return None
    test_data = JsonExtractor.extract_json(raw_output)
    questions = [Question(question=q.get("question"), options=q.get("options", {})) for q in test_data.get("questions", [])]
    return Test(test_name=test_data.get("test-name", "Unnamed Test"), topic=test_data.get("topic", topic), questions=questions)


def evaluate_answers_service(questions, user_answers, is_open, language):
    answer_checker = AnswerChecker(ask_ai)
    detailed_results = []
    for i, answer_item in enumerate(user_answers):
        q_obj = questions[i]
        assessment = answer_checker.check(q_obj.question, answer_item['answer'], q_obj.options, is_open, language)
        detailed_results.append({"question": q_obj.question, "answer": answer_item['answer'], "assessment": assessment})
    return detailed_results

def calculate_final_score_service(detailed_results):
    prompt = "Based on these answers and evaluations, give a final score from 0-100:\n\n"
    for i, result in enumerate(detailed_results, 1):
        prompt += f"Q{i}: {result['question']}\nA{i}: {result['answer']}\nAssessment: {result['assessment']}\n\n"
    prompt += "Return just the number."
    result_text = ask_ai(prompt)
    return int(''.join(filter(str.isdigit, result_text))) if result_text else 0

# --- Course and Lesson Services ---
def create_course_service(user, topic, final_score, assessed_answers):
    prompt = CoursePromptBuilder.build_course_structure_prompt(topic, final_score, assessed_answers, user.language, user.preferred_lesson_length)
    raw_course = ask_ai(prompt)
    if not raw_course:
        return None
    course_json = JsonExtractor.extract_json(raw_course)

    new_course = Course(user_id=user.id, course_title=course_json.get('course_title', f"Course on {topic}"), course_data=course_json)
    db.session.add(new_course)
    db.session.commit() # Commit to get the new_course.id

    for unit in course_json.get('units', []):
        for lesson_data in unit.get('lessons', []):
            new_lesson = Lesson(course_id=new_course.id, unit_title=unit.get('unit_title'), lesson_title=lesson_data.get('lesson_title'))
            db.session.add(new_lesson)
    db.session.commit()
    return new_course

def generate_lesson_content_service(lesson, user):
    if lesson.html_content:
        return

    prompt = LessonPromptBuilder.build_lesson_content_prompt(lesson.lesson_title, lesson.unit_title, user.language, user.preferred_lesson_length)
    markdown_text = ask_ai(prompt)
    if not markdown_text:
        return

    processed_text = re.sub(r'\[IMAGE_PROMPT:\s*"(.*?)"\]', r'<i>[Image Prompt: "\1"]</i>', markdown_text)
    lesson.html_content = markdown.markdown(processed_text, extensions=["fenced_code", "tables"])
    db.session.commit()