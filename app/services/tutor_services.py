from app.ai_clients import ask_gemini_stream
from models.prompt_builders import ChatPromptBuilder

def get_tutor_response_service(lesson, chat_history, user_question, user):
    lesson_content = lesson.html_content or "Lesson content has not been generated yet."
    prompt = ChatPromptBuilder.build_tutor_prompt(
        lesson_content=lesson_content,
        unit_title=lesson.unit_title,
        chat_history=chat_history,
        user_question=user_question,
        language=user.language
    )
    return ask_gemini_stream(prompt)
