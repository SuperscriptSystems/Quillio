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

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")


# --- AI Interaction Function ---
def ask_ai(prompt, model="gemini-1.5-flash", expect_json=True):
    """
    Sends a prompt to the Google Gemini API using a specified model.
    Note: User requested specific model versions. Using the latest available stable versions.
    - 'gemini-1.5-flash' for tests and assessments.
    - 'gemini-1.5-pro' for course and lesson generation.
    """
    if not GEMINI_API_KEY:
        print("Error: GEMINI_API_KEY environment variable is not set.")
        return "Configuration Error: The server's API key is not set."

    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={GEMINI_API_KEY}"
    headers = {'Content-Type': 'application/json'}

    generation_config = {
        "temperature": 0.7,
        "maxOutputTokens": 4096, # Increased token limit for Pro model
    }
    if expect_json:
        generation_config["response_mime_type"] = "application/json"

    data = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": generation_config
    }

    try:
        response = requests.post(url, headers=headers, data=json.dumps(data))
        response.raise_for_status()

        result = response.json()

        if 'candidates' in result and result['candidates'][0]['content']['parts'][0]['text']:
            return result['candidates'][0]['content']['parts'][0]['text']
        else:
            error_message = f"Content generation failed or was blocked. Response: {result}"
            print(error_message)
            return error_message

    except requests.exceptions.RequestException as e:
        print(f"Error communicating with Gemini API: {e}")
        if e.response:
            print(f"Error Response Body: {e.response.text}")
        return "Error: Could not connect to the AI service."
    except (KeyError, IndexError) as e:
        print(f"Error parsing Gemini API response: {e}. Full response: {response.json()}")
        return "Error: Invalid response format from the AI service."


# --- Test and Assessment Services ---
def generate_test_service(topic, format_type, additional_context, language):
    if format_type == "multiple_choice":
        prompt = TestPromptBuilder.build_multiple_choice_prompt(topic, additional_context, language)
    else:
        prompt = TestPromptBuilder.build_open_question_prompt(topic, additional_context, language)

    raw_output = ask_ai(prompt, model="gemini-1.5-flash")
    if not raw_output or "Error:" in raw_output:
        print(f"Failed to generate test. AI response: {raw_output}")
        return None
    test_data = JsonExtractor.extract_json(raw_output)
    questions = [Question(question=q.get("question"), options=q.get("options", {})) for q in
                 test_data.get("questions", [])]
    return Test(test_name=test_data.get("test-name", "Unnamed Test"), topic=test_data.get("topic", topic),
                questions=questions)


def evaluate_answers_service(questions, user_answers, is_open, language):
    answer_checker = AnswerChecker(lambda p: ask_ai(p, model="gemini-1.5-flash", expect_json=False))
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
    result_text = ask_ai(prompt, model="gemini-1.5-flash", expect_json=False)
    return int(''.join(filter(str.isdigit, result_text))) if result_text and "Error:" not in result_text else 0


# --- Course and Lesson Services ---
def create_course_service(user, topic, final_score, assessed_answers):
    prompt = CoursePromptBuilder.build_course_structure_prompt(topic, final_score, assessed_answers, user.language,
                                                               user.preferred_lesson_length)
    raw_course = ask_ai(prompt, model="gemini-1.5-pro")
    if not raw_course or "Error:" in raw_course:
        print(f"Failed to create course. AI response: {raw_course}")
        return None
    course_json = JsonExtractor.extract_json(raw_course)

    new_course = Course(user_id=user.id, course_title=course_json.get('course_title', f"Course on {topic}"),
                        course_data=course_json)
    db.session.add(new_course)
    db.session.commit()

    for unit in course_json.get('units', []):
        for lesson_data in unit.get('lessons', []):
            new_lesson = Lesson(course_id=new_course.id, unit_title=unit.get('unit_title'),
                                lesson_title=lesson_data.get('lesson_title'))
            db.session.add(new_lesson)
    db.session.commit()
    return new_course


def generate_lesson_content_service(lesson, user):
    if lesson.html_content:
        return

    prompt = LessonPromptBuilder.build_lesson_content_prompt(lesson.lesson_title, lesson.unit_title, user.language,
                                                             user.preferred_lesson_length)
    markdown_text = ask_ai(prompt, model="gemini-1.5-pro", expect_json=False)
    if not markdown_text or "Error:" in markdown_text:
        print(f"Failed to generate lesson content. AI response: {markdown_text}")
        lesson.html_content = "<p>Error generating lesson content. Please try again later.</p>"
        db.session.commit()
        return

    processed_text = re.sub(r'\[IMAGE_PROMPT:\s*"(.*?)"\]', r'<i>[Image Prompt: "\1"]</i>', markdown_text)
    lesson.html_content = markdown.markdown(processed_text, extensions=["fenced_code", "tables"])
    db.session.commit()