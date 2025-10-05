import json
from models.json_extractor import JsonExtractor
from models.fulltest import Test
from models.question import Question
from app.ai_clients import ask_gemini
from .utils import update_token_count
from models.prompt_builders import TestPromptBuilder, AnswerPromptBuilder

def generate_test_service(topic, format_type, additional_context, language, user_profile=None, lesson_content_context=""):
    prompt = TestPromptBuilder.build_multiple_choice_prompt(
        topic, additional_context, language,
        user_profile=user_profile,
        lesson_content_context=lesson_content_context
    )
    raw_output, tokens = ask_gemini(prompt, json_mode=True)
    update_token_count(tokens)

    if not raw_output or "Error:" in raw_output:
        print(f"Failed to generate test with Gemini. AI response: {raw_output}")
        return None

    test_data = JsonExtractor.extract_json(raw_output)
    questions = [
        Question(question=q.get("question"), options=q.get("options", {}))
        for q in test_data.get("questions", [])
    ]

    return Test(
        test_name=test_data.get("test-name", "Unnamed Test"),
        topic=test_data.get("topic", topic),
        questions=questions
    )


def evaluate_answers_service(questions, user_answers, language):
    qa_list = []
    for q, ua in zip(questions, user_answers):
        answer_key = ua.get('answer_value', ua.get('answer', ''))
        answer_text = ua.get('answer', '')
        if hasattr(q, 'options') and answer_key in q.options:
            answer_text = q.options[answer_key]
        qa_list.append({
            "question": q.question,
            "answer": answer_text,
            "original_answer": answer_key
        })

    from app.ai_clients import ask_gemini
    prompt = AnswerPromptBuilder.build_batch_check_prompt(
        [{"question": qa["question"], "answer": qa["answer"]} for qa in qa_list],
        language
    )
    response_text, tokens = ask_gemini(prompt, json_mode=True)
    update_token_count(tokens)

    if not response_text or "Error:" in response_text:
        return []

    try:
        response_json = JsonExtractor.extract_json(response_text)
        assessments = response_json.get("assessments", [])
        detailed_results = []

        for i, qa in enumerate(qa_list):
            assessment = next(
                (item['assessment'] for item in assessments if item['id'] == i),
                "Evaluation Error"
            )
            detailed_results.append({
                "question": qa["question"],
                "answer": qa["answer"],
                "original_answer": qa["original_answer"],
                "assessment": assessment
            })
        return detailed_results

    except (ValueError, KeyError) as e:
        print(f"Error parsing Gemini batch assessment response: {e}")
        return []


def calculate_percentage_score_service(detailed_results):
    from app.ai_clients import ask_gemini
    prompt = "Based on these answers and evaluations, give a final score from 0-100:\n\n"
    for result in detailed_results:
        prompt += f"Q: {result['question']}\nA: {result['answer']}\nAssessment: {result['assessment']}\n\n"
    prompt += "Return just the number."
    result_text, tokens = ask_gemini(prompt, json_mode=False)
    update_token_count(tokens)

    return int(''.join(filter(str.isdigit, result_text))) if result_text and "Error:" not in result_text else 0
