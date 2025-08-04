import json
import re
import markdown
from app.ask_ai import ask_ai
from models.prompt_builders import TestPromptBuilder, AnswerPromptBuilder, CoursePromptBuilder, LessonPromptBuilder
from models.json_extractor import JsonExtractor
from models.fulltest import Test
from models.question import Question
from app.models import db, Course, Lesson


# --- Test and Assessment Services ---
def generate_test_service(topic, format_type, additional_context, language):
    if format_type == "multiple_choice":
        prompt = TestPromptBuilder.build_multiple_choice_prompt(topic, additional_context, language)
    else:
        prompt = TestPromptBuilder.build_open_question_prompt(topic, additional_context, language)

    raw_output = ask_ai(prompt, model="gpt-4o-mini", json_mode=True)
    if not raw_output or "Error:" in raw_output:
        print(f"Failed to generate test. AI response: {raw_output}")
        return None
    test_data = JsonExtractor.extract_json(raw_output)
    questions = [Question(question=q.get("question"), options=q.get("options", {})) for q in
                 test_data.get("questions", [])]
    return Test(test_name=test_data.get("test-name", "Unnamed Test"), topic=test_data.get("topic", topic),
                questions=questions)


def evaluate_answers_service(questions, user_answers, language):
    """
    Evaluates all user answers in a single, efficient batch API call.
    """

    questions_and_answers = []
    for i, q_obj in enumerate(questions):
        questions_and_answers.append({
            "question": q_obj.question,
            "answer": user_answers[i]['answer']
        })

    prompt = AnswerPromptBuilder.build_batch_check_prompt(questions_and_answers, language)


    response_text = ask_ai(prompt, model="gpt-4o-mini", json_mode=True)
    if not response_text or "Error:" in response_text:
        print(f"Failed to evaluate answers in batch. AI response: {response_text}")
        return []

    try:
        response_json = JsonExtractor.extract_json(response_text)
        assessments = response_json.get("assessments", [])

        detailed_results = []
        for i, qa in enumerate(questions_and_answers):
            detailed_results.append({
                "question": qa["question"],
                "answer": qa["answer"],
                "assessment": next((item['assessment'] for item in assessments if item['id'] == i), "Evaluation Error")
            })
        return detailed_results
    except (ValueError, KeyError) as e:
        print(f"Error parsing batch assessment response: {e}")
        return []


def generate_knowledge_assessment_service(detailed_results):
    """Generates a qualitative written assessment of the user's knowledge."""
    prompt = "Provide a concise, one or two paragraph assessment of the user's knowledge of the topic based on the test results below. Speak directly to the user (e.g., 'Your responses indicate...'). Do not use markdown.\n\n"
    for i, result in enumerate(detailed_results, 1):
        prompt += f"Q{i}: {result['question']}\nA{i}: {result['answer']}\nAssessment: {result['assessment']}\n\n"


    assessment_text = ask_ai(prompt, model="gpt-4o-mini", json_mode=False)
    return assessment_text if assessment_text and "Error:" not in assessment_text else "Could not generate assessment."


def calculate_percentage_score_service(detailed_results):
    """Calculates a numerical score from 0-100 based on assessments (for unit tests)."""
    prompt = "Based on these answers and evaluations, give a final score from 0-100:\n\n"
    for i, result in enumerate(detailed_results, 1):
        prompt += f"Q{i}: {result['question']}\nA{i}: {result['answer']}\nAssessment: {result['assessment']}\n\n"
    prompt += "Return just the number."


    result_text = ask_ai(prompt, model="gpt-4o-mini", json_mode=False)
    return int(''.join(filter(str.isdigit, result_text))) if result_text and "Error:" not in result_text else 0


# --- Course and Lesson Services ---
def create_course_service(user, topic, knowledge_assessment, assessed_answers):
    prompt = CoursePromptBuilder.build_course_structure_prompt(topic, knowledge_assessment, assessed_answers,
                                                               user.language,
                                                               user.preferred_lesson_length)
    raw_course = ask_ai(prompt, model="gpt-4o", json_mode=True)
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
    markdown_text = ask_ai(prompt, model="gpt-4o", json_mode=False)
    if not markdown_text or "Error:" in markdown_text:
        print(f"Failed to generate lesson content. AI response: {markdown_text}")
        lesson.html_content = "<p>Error generating lesson content. Please try again later.</p>"
        db.session.commit()
        return

    processed_text = re.sub(r'\[IMAGE_PROMPT:\s*"(.*?)"\]', r'<i>[Image Prompt: "\1"]</i>', markdown_text)
    lesson.html_content = markdown.markdown(processed_text, extensions=["fenced_code", "tables"])
    db.session.commit()