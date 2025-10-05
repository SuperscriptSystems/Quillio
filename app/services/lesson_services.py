import re
import markdown
from flask import url_for
from app.ai_clients import ask_ai_stream
from app.models import db, Lesson
from models.prompt_builders import LessonPromptBuilder

def generate_lesson_content_service(lesson, user):
    user_profile = {'age': user.age, 'bio': user.bio}
    course_structure = lesson.course.course_data

    prompt = LessonPromptBuilder.build_lesson_content_prompt(
        lesson.lesson_title, lesson.unit_title, user.language, user.preferred_lesson_length,
        user_profile=user_profile, course_structure=course_structure
    )

    def content_generator():
        response_stream = ask_ai_stream(prompt, model="gpt-4o")
        full_markdown_chunks = []

        for chunk in response_stream:
            yield chunk
            full_markdown_chunks.append(chunk)

        full_markdown_text = "".join(full_markdown_chunks)
        if "Error:" in full_markdown_text:
            lesson.html_content = "<p>Error generating lesson content. Please try again later.</p>"
        else:
            next_up_link_md = _generate_next_up_link(lesson, user)
            final_md = full_markdown_text + next_up_link_md
            processed_text = re.sub(r'\[IMAGE_PROMPT:\s*"(.*?)"\]', r'<i>[Image Prompt: "\1"]</i>', final_md)
            lesson.html_content = markdown.markdown(processed_text, extensions=["fenced_code", "tables"])

        if not lesson.is_completed:
            lesson.is_completed = True
            course = lesson.course
            course.completed_lessons = Lesson.query.filter_by(course_id=course.id, is_completed=True).count()

        db.session.commit()

    return content_generator()


def _generate_next_up_link(lesson, user):
    course = lesson.course
    lang = user.language
    try:
        units = course.course_data.get('units', [])
        current_unit_index, current_unit = next(
            ((i, u) for i, u in enumerate(units) if u['unit_title'] == lesson.unit_title), (None, None))
        if not current_unit:
            return ""

        lessons = current_unit.get('lessons', [])
        current_index = next(
            (i for i, l in enumerate(lessons) if l['lesson_title'] == lesson.lesson_title), None)
        if current_index is None:
            return ""

        if current_index + 1 < len(lessons):
            next_lesson = lessons[current_index + 1]
            next_lesson_obj = Lesson.query.filter_by(course_id=course.id,
                                                     lesson_title=next_lesson.get('lesson_title')).first()
            if next_lesson_obj:
                url = url_for('loading_lesson', lesson_id=next_lesson_obj.id, _external=True)
                return f"\n\n<hr>\n\n### 👉 {'Далее' if lang == 'russian' else 'Next up'}: [{next_lesson['lesson_title']}]({url})"

        test_data = current_unit.get('test')
        if test_data and test_data.get('test_title'):
            url = url_for('loading_unit_test', course_id=course.id,
                          unit_title=current_unit['unit_title'], test_title=test_data['test_title'], _external=True)
            return f"\n\n<hr>\n\n### 👉 {'Далее' if lang == 'russian' else 'Next up'}: [{test_data['test_title']}]({url})"
    except Exception as e:
        print(f"Error generating 'Next up' link: {e}")
    return ''
