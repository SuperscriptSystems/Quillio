import json
import re
import time
import markdown
from flask import url_for
from flask_login import current_user
from flask import session
from app.ai_clients import ask_ai, ask_ai_stream, ask_gemini, ask_gemini_stream
from models.prompt_builders import TestPromptBuilder, AnswerPromptBuilder, CoursePromptBuilder, LessonPromptBuilder, \
    ChatPromptBuilder, CourseEditorPromptBuilder
from models.json_extractor import JsonExtractor
from models.fulltest import Test
from models.question import Question
from app.models import db, Course, Lesson


def _update_token_count(tokens_to_add):
    """Helper function to add tokens to the current user's total."""
    if tokens_to_add > 0:
        current_user.tokens_used += tokens_to_add
        db.session.commit()


# --- Test and Assessment Services (Using Gemini) ---
def generate_test_service(topic, format_type, additional_context, language, user_profile=None,
                          lesson_content_context=""):
    """Generates a test using the Gemini model and updates token count."""
    prompt = TestPromptBuilder.build_multiple_choice_prompt(topic, additional_context, language,
                                                            user_profile=user_profile,
                                                            lesson_content_context=lesson_content_context)
    raw_output, tokens = ask_gemini(prompt, json_mode=True)
    _update_token_count(tokens)

    if not raw_output or "Error:" in raw_output:
        print(f"Failed to generate test with Gemini. AI response: {raw_output}")
        return None
    test_data = JsonExtractor.extract_json(raw_output)
    questions = [Question(question=q.get("question"), options=q.get("options", {})) for q in
                 test_data.get("questions", [])]
    return Test(test_name=test_data.get("test-name", "Unnamed Test"), topic=test_data.get("topic", topic),
                questions=questions)


def evaluate_answers_service(questions, user_answers, language):
    """Evaluates answers using the Gemini model and updates token count."""
    qa_list = [{"question": q.question, "answer": ua['answer']} for q, ua in zip(questions, user_answers)]
    prompt = AnswerPromptBuilder.build_batch_check_prompt(qa_list, language)
    response_text, tokens = ask_gemini(prompt, json_mode=True)
    _update_token_count(tokens)

    if not response_text or "Error:" in response_text:
        return []

    try:
        response_json = JsonExtractor.extract_json(response_text)
        assessments = response_json.get("assessments", [])
        detailed_results = [{"question": qa["question"], "answer": qa["answer"],
                             "assessment": next((item['assessment'] for item in assessments if item['id'] == i),
                                                "Evaluation Error")} for i, qa in enumerate(qa_list)]
        return detailed_results
    except (ValueError, KeyError) as e:
        print(f"Error parsing Gemini batch assessment response: {e}")
        return []


def calculate_percentage_score_service(detailed_results):
    """Calculates a score using the Gemini model and updates token count."""
    prompt = "Based on these answers and evaluations, give a final score from 0-100:\n\n"
    for result in detailed_results:
        prompt += f"Q: {result['question']}\nA: {result['answer']}\nAssessment: {result['assessment']}\n\n"
    prompt += "Return just the number."
    result_text, tokens = ask_gemini(prompt, json_mode=False)
    _update_token_count(tokens)

    return int(''.join(filter(str.isdigit, result_text))) if result_text and "Error:" not in result_text else 0


# --- Course and Lesson Services (Using OpenAI) ---
def generate_knowledge_assessment_service(detailed_results):
    """Generates a qualitative knowledge assessment using OpenAI and updates token count."""
    prompt = "Provide a concise, one or two paragraph assessment of the user's knowledge of the topic based on the test results below. Do not address the user directly; use third-person phrasing (e.g., 'users responses indicate...'). Do not use markdown.\n\n"
    for result in detailed_results:
        prompt += f"Q: {result['question']}\nA: {result['answer']}\nAssessment: {result['assessment']}\n\n"
    assessment_text, tokens = ask_ai(prompt, model="gpt-4o-mini", json_mode=False)
    _update_token_count(tokens)

    return assessment_text if assessment_text and "Error:" not in assessment_text else "Could not generate assessment."


def create_course_service(user, topic, knowledge_assessment, assessed_answers):
    """Creates a course structure using OpenAI and updates token count."""
    prompt = CoursePromptBuilder.build_course_structure_prompt(
        topic, knowledge_assessment, assessed_answers, user.language, user)
    raw_output, tokens = ask_ai(prompt, json_mode=True)
    _update_token_count(tokens)

    if not raw_output or "Error:" in raw_output:
        print(f"Failed to generate course structure. AI response: {raw_output}")
        return None

    course_data = JsonExtractor.extract_json(raw_output)
    if not course_data:
        print("Failed to parse course structure from AI response.")
        return None

    # Generate improved course name and use it as the main title
    original_name = course_data.get("course_title", topic)
    improved_name = generate_improved_course_name(original_name)
    
    # Update the course title in the course data
    course_data['course_title'] = improved_name

    # Create the course with the improved name
    course = Course(
        user_id=user.id,
        course_title=improved_name,
        course_data=course_data
    )
    db.session.add(course)
    db.session.commit()  # Commit to get the course ID

    for unit in course_data.get('units', []):
        for lesson_data in unit.get('lessons', []):
            new_lesson = Lesson(course_id=course.id, unit_title=unit.get('unit_title'),
                                lesson_title=lesson_data.get('lesson_title'))
            db.session.add(new_lesson)
    db.session.commit()
    return course
    return new_course


def generate_lesson_content_service(lesson, user):
    """
    Generates lesson content by streaming, saves the final result to the DB,
    and returns a generator that yields the content chunks.
    """
    user_profile = {'age': user.age, 'bio': user.bio}
    course_structure = lesson.course.course_data

    prompt = LessonPromptBuilder.build_lesson_content_prompt(
        lesson.lesson_title, lesson.unit_title, user.language, user.preferred_lesson_length, user_profile=user_profile,
        course_structure=course_structure
    )

    def content_generator():
        # Using ask_openai_stream
        response_stream = ask_ai_stream(prompt, model="gpt-4o")

        full_markdown_chunks = []
        for chunk in response_stream:
            yield chunk  # Yield each piece of content to the client immediately
            full_markdown_chunks.append(chunk)

        # After the stream is complete, process and save the full content
        print("Stream finished. Processing and saving full lesson content...")
        full_markdown_text = "".join(full_markdown_chunks)

        if "Error:" in full_markdown_text:
            lesson.html_content = "<p>Error generating lesson content. Please try again later.</p>"
        else:
            next_up_link_md = _generate_next_up_link(lesson, user)
            final_markdown_text = full_markdown_text + next_up_link_md
            processed_text = re.sub(r'\[IMAGE_PROMPT:\s*"(.*?)"\]', r'<i>[Image Prompt: "\1"]</i>', final_markdown_text)
            lesson.html_content = markdown.markdown(processed_text, extensions=["fenced_code", "tables"])

        # Update lesson and course completion status
        if not lesson.is_completed:
            lesson.is_completed = True
            course = lesson.course
            # Recalculate completed lessons count
            course.completed_lessons = Lesson.query.filter_by(course_id=course.id, is_completed=True).count()

        db.session.commit()
        print(f"Lesson {lesson.id} saved to database.")

    return content_generator()


def generate_improved_course_name(original_name):
    """Generate an improved, concise and informative course name using AI."""
    prompt = f"Improve this course name to be more concise and informative. Keep it under 60 characters. Original name: {original_name}. Return ONLY the improved name, no quotes or additional text."
    
    # Try Gemini first, fall back to OpenAI if needed
    improved_name, tokens = ask_gemini(prompt)
    if not improved_name or "Error:" in improved_name:
        improved_name, tokens = ask_ai(prompt)
        
    _update_token_count(tokens)
    
    # Clean up the response
    improved_name = improved_name.strip('"\'').strip()
    return improved_name if improved_name and len(improved_name) > 0 else original_name


def _generate_next_up_link(lesson, user):
    course = lesson.course
    course_data = course.course_data
    lang = user.language
    try:
        units = course_data.get('units', [])
        current_unit_index, current_unit = next(
            ((i, u) for i, u in enumerate(units) if u['unit_title'] == lesson.unit_title), (None, None))
        if current_unit is None: return ""
        lessons_in_unit = current_unit.get('lessons', [])
        current_lesson_index = next(
            (i for i, l in enumerate(lessons_in_unit) if l['lesson_title'] == lesson.lesson_title), None)
        if current_lesson_index is None: return ""
        url = None
        link_text = ""
        if current_lesson_index + 1 < len(lessons_in_unit):
            next_lesson_data = lessons_in_unit[current_lesson_index + 1]
            next_lesson_title = next_lesson_data.get('lesson_title')
            next_lesson_obj = Lesson.query.filter_by(course_id=course.id, lesson_title=next_lesson_title).first()
            if next_lesson_obj:
                url = url_for('loading_lesson', lesson_id=next_lesson_obj.id, _external=True)
                link_text = next_lesson_title
        else:
            test_data = current_unit.get('test')
            if test_data and test_data.get('test_title'):
                url = url_for('loading_unit_test', course_id=course.id, unit_title=current_unit.get('unit_title'),
                              test_title=test_data.get('test_title'), _external=True)
                link_text = test_data.get('test_title')
        if url and link_text:
            next_up_header = "Далее" if lang == 'russian' else "Next up"
            return f"\n\n<hr>\n\n### 👉 {next_up_header}: [{link_text}]({url})"
    except Exception as e:
        print(f"Error generating 'Next up' link: {e}")
    return ''


def get_tutor_response_service(lesson, chat_history, user_question, user):
    """Gets a contextual response from the AI tutor by streaming."""
    lesson_content = lesson.html_content if lesson.html_content else "Lesson content has not been generated yet."

    tutor_prompt = ChatPromptBuilder.build_tutor_prompt(
        lesson_content=lesson_content,
        unit_title=lesson.unit_title,
        chat_history=chat_history,
        user_question=user_question,
        language=user.language
    )

    # Returns a generator that yields response chunks
    return ask_gemini_stream(tutor_prompt)


def edit_course_service(course, user_request, language):
    """Uses an AI to edit the course structure and syncs the database."""
    print(f"[DEBUG] edit_course_service called with request: {user_request}")
    
    # Check if this is a title update request
    title_keywords = ["title", "name", "rename", "call this"]
    is_title_update = any(keyword in user_request.lower() for keyword in title_keywords)
    
    if is_title_update and "course_title" in course.course_data:
        print("[DEBUG] Processing title update request")
        # For title updates, use a fast model to generate an improved title
        prompt = CourseEditorPromptBuilder.build_title_improvement_prompt(
            user_request, language
        )
        new_title, tokens = ask_ai(prompt, model="gpt-4o-mini", json_mode=False)
        _update_token_count(tokens)
        
        if new_title and "Error:" not in new_title:
            # Clean up the title (remove quotes, extra spaces, etc.)
            new_title = new_title.strip('\'" ')
            print(f"[DEBUG] Generated new title: {new_title}")
            # Update the course data with the new title
            course_data = course.course_data
            course_data["course_title"] = new_title
            course.course_data = course_data
            db.session.commit()
            return course_data, None
        else:
            error_msg = f"Failed to generate an improved title. Response: {new_title}"
            print(f"[ERROR] {error_msg}")
            return None, error_msg
    
    print("[DEBUG] Processing full course edit request")
    # For non-title updates, use the full course editor
    prompt = CourseEditorPromptBuilder.build_edit_prompt(course.course_data, user_request, language)
    new_course_str, tokens = ask_ai(prompt, model="gpt-4o", json_mode=True)
    _update_token_count(tokens)

    if not new_course_str or "Error:" in new_course_str:
        error_msg = f"AI failed to generate a new course structure. Response: {new_course_str}"
        print(f"[ERROR] {error_msg}")
        return None, error_msg

    try:
        print("[DEBUG] Parsing AI response")
        new_course_json = JsonExtractor.extract_json(new_course_str)
        if 'course_title' not in new_course_json or 'units' not in new_course_json:
            error_msg = f"Invalid JSON structure returned by AI: {new_course_json}"
            print(f"[ERROR] {error_msg}")
            raise ValueError(error_msg)
    except Exception as e:
        error_msg = f"Error parsing new course structure: {str(e)}"
        print(f"[ERROR] {error_msg}")
        return None, error_msg

    try:
        print("[DEBUG] Updating database with new course structure")
        # --- Sync Database with new structure ---
        # 1. Update the main course data
        course.course_data = new_course_json

        # 2. Get a set of all lesson titles from the new JSON
        new_lesson_titles = set()
        for unit in new_course_json.get('units', []):
            for lesson_data in unit.get('lessons', []):
                if 'lesson_title' in lesson_data:
                    new_lesson_titles.add(lesson_data['lesson_title'])
                else:
                    print(f"[WARNING] Missing 'lesson_title' in lesson data: {lesson_data}")

        # 3. Get all existing Lesson objects for this course
        existing_lessons = Lesson.query.filter_by(course_id=course.id).all()
        existing_lesson_titles = {lesson.lesson_title: lesson for lesson in existing_lessons}

        # 4. Delete lessons that are no longer in the new structure
        for title, lesson_obj in existing_lesson_titles.items():
            if title not in new_lesson_titles:
                print(f"[DEBUG] Deleting lesson: {title}")
                db.session.delete(lesson_obj)

        # 5. Add lessons that are new
        for unit in new_course_json.get('units', []):
            for lesson_data in unit.get('lessons', []):
                title = lesson_data.get('lesson_title')
                if title and title not in existing_lesson_titles:
                    print(f"[DEBUG] Adding new lesson: {title}")
                    new_lesson = Lesson(
                        course_id=course.id,
                        unit_title=unit.get('unit_title'),
                        lesson_title=title
                    )
                    db.session.add(new_lesson)

        # Recalculate completed lessons count
        course.completed_lessons = Lesson.query.filter_by(course_id=course.id, is_completed=True).count()
        db.session.commit()
        print("[DEBUG] Course update completed successfully")
        return new_course_json, None
        
    except Exception as e:
        db.session.rollback()
        error_msg = f"Database error during course update: {str(e)}"
        print(f"[ERROR] {error_msg}")
        import traceback
        traceback.print_exc()
        return None, error_msg