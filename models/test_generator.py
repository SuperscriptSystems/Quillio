from models.json_extractor import JsonExtractor
from models.question import Question
from models.prompt_builders import TestPromptBuilder
from models.fulltest import Test

class TestGenerator:
    def __init__(self, ask_ai_function):
        self.ask_ai = ask_ai_function

    def generate_multiple_choice_test(self, topic, additional_prompt="", language="english"):
        prompt = TestPromptBuilder.build_multiple_choice_prompt(topic, additional_prompt, language)
        response = self._get_ai_test_data(prompt)
        return self._create_test_from_data(response, topic, is_open=False)

    def generate_open_test(self, topic, additional_prompt="", language="english"):
        prompt = TestPromptBuilder.build_open_question_prompt(topic, additional_prompt, language)
        response = self._get_ai_test_data(prompt)
        return self._create_test_from_data(response, topic, is_open=True)

    def _get_ai_test_data(self, prompt):
        raw_output = self.ask_ai(prompt)
        return JsonExtractor.extract_json(raw_output)

    def _create_test_from_data(self, data, default_topic, is_open, test_id = 1):
        test_pages = [
            self._create_testpage_from_data(data, i, test_id, is_open)
            for i in range(len(data.get("questions", [])))
        ]

        return Test(
            test_name=data.get("test-name", "Unnamed Test"),
            topic=data.get("topic", default_topic),
            questions=test_pages
        )

    def _create_testpage_from_data(self, data, question_number, test_id, is_open):
        question_data = data["questions"][question_number]
        return Question(
            test_id=test_id,
            question=question_data["question"],
            options={"answer": ""} if is_open else question_data.get("options", {})
        )