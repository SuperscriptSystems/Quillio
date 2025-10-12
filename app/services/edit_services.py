from app.models import db, Lesson
from app.ai_clients import ask_ai
from models.json_extractor import JsonExtractor
from models.prompt_builders import CourseEditorPromptBuilder
from .utils import update_token_count

def edit_course_service(course, user_request, language):
    print(f"[DEBUG] edit_course_service called with request: {user_request}")

    title_keywords = ["title", "name", "rename", "call this"]
    is_title_update = any(k in user_request.lower() for k in title_keywords)

    if is_title_update and "course_title" in course.course_data:
        print("[DEBUG] Processing title update request")
        prompt = CourseEditorPromptBuilder.build_title_improvement_prompt(
            course.course_data["course_title"], language
        )
        
        try:
            new_title, tokens = ask_ai(prompt, model="gemini-2.5-flash", json_mode=False)
            update_token_count(tokens)

            if new_title and "Error:" not in new_title:
                new_title = new_title.strip('\'" ')
                course_data = course.course_data
                course_data["course_title"] = new_title
                course.course_data = course_data
                db.session.commit()
                return course_data, None
            else:
                err = f"Failed to generate an improved title. Response: {new_title}"
                print(f"[ERROR] {err}")
                return None, err
        except Exception as e:
            err = f"Error calling AI service for title update: {str(e)}"
            print(f"[ERROR] {err}")
            return None, err

    print("[DEBUG] Processing full course edit request")
    prompt = CourseEditorPromptBuilder.build_edit_prompt(course.course_data, user_request, language)
    
    try:
        new_course_str, tokens = ask_ai(prompt, model="gemini-2.5-flash", json_mode=True)
        update_token_count(tokens)

        if not new_course_str or "Error:" in new_course_str:
            err = f"AI failed to generate a new course structure. Response: {new_course_str}"
            print(f"[ERROR] {err}")
            return None, err

        try:
            new_course_json = JsonExtractor.extract_json(new_course_str)
            if 'course_title' not in new_course_json or 'units' not in new_course_json:
                raise ValueError(f"Invalid JSON structure returned by AI: {new_course_json}")
        except Exception as e:
            err = f"Error parsing new course structure: {str(e)}"
            print(f"[ERROR] {err}")
            return None, err

        try:
            course.course_data = new_course_json
            new_titles = {l['lesson_title'] for u in new_course_json['units'] for l in u.get('lessons', []) if 'lesson_title' in l}

            existing_lessons = {l.lesson_title: l for l in Lesson.query.filter_by(course_id=course.id).all()}
            for title, obj in existing_lessons.items():
                if title not in new_titles:
                    db.session.delete(obj)

            for u in new_course_json['units']:
                for l in u.get('lessons', []):
                    t = l.get('lesson_title')
                    if t and t not in existing_lessons:
                        db.session.add(Lesson(course_id=course.id, unit_title=u['unit_title'], lesson_title=t))

            course.completed_lessons = Lesson.query.filter_by(course_id=course.id, is_completed=True).count()
            db.session.commit()
            print("[DEBUG] Course update completed successfully")
            return new_course_json, None

        except Exception as e:
            db.session.rollback()
            err = f"Database error during course update: {e}"
            print(f"[ERROR] {err}")
            import traceback
            traceback.print_exc()
            return None, err

    except Exception as e:
        err = f"Error calling AI service for course edit: {str(e)}"
        print(f"[ERROR] {err}")
        return None, err
