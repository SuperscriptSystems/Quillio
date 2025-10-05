from app.ai_clients import ask_ai, ask_gemini
from app.models import db, Course, Lesson
from models.json_extractor import JsonExtractor
from models.prompt_builders import CoursePromptBuilder
from .utils import update_token_count
from .test_services import calculate_percentage_score_service

def generate_knowledge_assessment_service(detailed_results):
    prompt = ("Provide a concise, one or two paragraph assessment of the user's knowledge "
              "of the topic based on the test results below. Do not address the user directly; "
              "use third-person phrasing. Do not use markdown.\n\n")
    for result in detailed_results:
        prompt += f"Q: {result['question']}\nA: {result['answer']}\nAssessment: {result['assessment']}\n\n"

    assessment_text, tokens = ask_ai(prompt, model="gpt-4o-mini", json_mode=False)
    update_token_count(tokens)
    return assessment_text if assessment_text and "Error:" not in assessment_text else "Could not generate assessment."


def create_course_service(user, topic, knowledge_assessment, assessed_answers):
    prompt = CoursePromptBuilder.build_course_structure_prompt(
        topic, knowledge_assessment, assessed_answers, user.language, user
    )
    raw_output, tokens = ask_ai(prompt, json_mode=True)
    update_token_count(tokens)

    if not raw_output or "Error:" in raw_output:
        print(f"Failed to generate course structure. AI response: {raw_output}")
        return None

    course_data = JsonExtractor.extract_json(raw_output)
    if not course_data:
        print("Failed to parse course structure from AI response.")
        return None

    from .course_services import generate_improved_course_name
    original_name = course_data.get("course_title", topic)
    improved_name = generate_improved_course_name(original_name)
    course_data['course_title'] = improved_name

    course = Course(user_id=user.id, course_title=improved_name, course_data=course_data)
    db.session.add(course)
    db.session.commit()

    for unit in course_data.get('units', []):
        for lesson_data in unit.get('lessons', []):
            new_lesson = Lesson(course_id=course.id,
                                unit_title=unit.get('unit_title'),
                                lesson_title=lesson_data.get('lesson_title'))
            db.session.add(new_lesson)
    db.session.commit()
    return course


def generate_improved_course_name(original_name):
    prompt = (f"Improve this course name to be more concise and informative. Keep it under 60 characters. "
              f"Original name: {original_name}. Return ONLY the improved name, no quotes or additional text.")
    improved_name, tokens = ask_gemini(prompt)
    if not improved_name or "Error:" in improved_name:
        improved_name, tokens = ask_ai(prompt)
    update_token_count(tokens)

    improved_name = improved_name.strip('"\'').strip()
    return improved_name if improved_name else original_name
