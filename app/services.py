import json
import re
import time
import markdown
from app.ai_clients import ask_openai, ask_gemini  # Updated import
from models.prompt_builders import TestPromptBuilder, AnswerPromptBuilder, CoursePromptBuilder, LessonPromptBuilder
from models.json_extractor import JsonExtractor
from models.fulltest import Test
from models.question import Question
from app.models import db, Course, Lesson


# --- Test and Assessment Services (Using Gemini) ---
def generate_test_service(topic, format_type, additional_context, language):
    """Generates a test using the Gemini model."""
    prompt = TestPromptBuilder.build_multiple_choice_prompt(topic, additional_context, language)

    # Using Gemini for test generation
    raw_output = ask_gemini(prompt, json_mode=True)

    if not raw_output or "Error:" in raw_output:
        print(f"Failed to generate test with Gemini. AI response: {raw_output}")
        return None
    test_data = JsonExtractor.extract_json(raw_output)
    questions = [Question(question=q.get("question"), options=q.get("options", {})) for q in
                 test_data.get("questions", [])]
    return Test(test_name=test_data.get("test-name", "Unnamed Test"), topic=test_data.get("topic", topic),
                questions=questions)


def evaluate_answers_service(questions, user_answers, language):
    """Evaluates answers using the Gemini model."""
    qa_list = [{"question": q.question, "answer": ua['answer']} for q, ua in zip(questions, user_answers)]
    prompt = AnswerPromptBuilder.build_batch_check_prompt(qa_list, language)

    # Using Gemini for answer evaluation
    response_text = ask_gemini(prompt, json_mode=True)

    if not response_text or "Error:" in response_text:
        print(f"Failed to evaluate answers with Gemini. AI response: {response_text}")
        return []

    try:
        response_json = JsonExtractor.extract_json(response_text)
        assessments = response_json.get("assessments", [])
        detailed_results = []
        for i, qa in enumerate(qa_list):
            assessment_text = next((item['assessment'] for item in assessments if item['id'] == i), "Evaluation Error")
            detailed_results.append({"question": qa["question"], "answer": qa["answer"], "assessment": assessment_text})
        return detailed_results
    except (ValueError, KeyError) as e:
        print(f"Error parsing Gemini batch assessment response: {e}")
        return []


def calculate_percentage_score_service(detailed_results):
    """Calculates a score using the Gemini model."""
    prompt = "Based on these answers and evaluations, give a final score from 0-100:\n\n"
    for result in detailed_results:
        prompt += f"Q: {result['question']}\nA: {result['answer']}\nAssessment: {result['assessment']}\n\n"
    prompt += "Return just the number."

    # Using Gemini for scoring
    result_text = ask_gemini(prompt, json_mode=False)

    return int(''.join(filter(str.isdigit, result_text))) if result_text and "Error:" not in result_text else 0


# --- Course and Lesson Services (Using OpenAI) ---
def generate_knowledge_assessment_service(detailed_results):
    """Generates a qualitative knowledge assessment using OpenAI's fast model."""
    prompt = "Provide a concise, one or two paragraph assessment of the user's knowledge of the topic based on the test results below. Speak directly to the user (e.g., 'Your responses indicate...'). Do not use markdown.\n\n"
    for result in detailed_results:
        prompt += f"Q: {result['question']}\nA: {result['answer']}\nAssessment: {result['assessment']}\n\n"

    # Using OpenAI's faster model for this quick summary
    assessment_text = ask_openai(prompt, model="gpt-4o-mini", json_mode=False)
    return assessment_text if assessment_text and "Error:" not in assessment_text else "Could not generate assessment."


def create_course_service(user, topic, knowledge_assessment, assessed_answers):
    """Creates a course structure using OpenAI's powerful model."""
    prompt = CoursePromptBuilder.build_course_structure_prompt(topic, knowledge_assessment, assessed_answers,
                                                               user.language, user.preferred_lesson_length)

    # Using OpenAI's more powerful model for course structure
    raw_course = ask_openai(prompt, model="gpt-4o", json_mode=True)

    if not raw_course or "Error:" in raw_course:
        print(f"Failed to create course with OpenAI. AI response: {raw_course}")
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
    """Generates lesson content using OpenAI's powerful model."""
    if lesson.html_content:
        return

    prompt = LessonPromptBuilder.build_lesson_content_prompt(lesson.lesson_title, lesson.unit_title, user.language,
                                                             user.preferred_lesson_length)

    # Using OpenAI's powerful model for lesson content
    markdown_text = ask_openai(prompt, model="gpt-4o", json_mode=False)

    if not markdown_text or "Error:" in markdown_text:
        print(f"Failed to generate lesson content with OpenAI. AI response: {markdown_text}")
        lesson.html_content = "<p>Error generating lesson content. Please try again later.</p>"
    else:
        processed_text = re.sub(r'\[IMAGE_PROMPT:\s*"(.*?)"\]', r'<i>[Image Prompt: "\1"]</i>', markdown_text)
        lesson.html_content = markdown.markdown(processed_text, extensions=["fenced_code", "tables"])

    db.session.commit()