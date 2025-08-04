class TestPromptBuilder:
    @staticmethod
    def build_multiple_choice_prompt(topic, additional_context="", language="english", number_of_questions=5):
        return f"""
            You are assessing a person's skill level in this topic: {topic}.
            {additional_context}

            Create {number_of_questions} multiple choice questions.
            Your entire response MUST be a valid JSON object.
            Generate the response in the following language: {language}.
            All user-visible string values (like test-name, topic, question, and option text) must be in {language}.
            Keep all JSON keys (like "test-name", "topic", "questions", "type", "options", "option1", etc.) in English.

            Use this format:

            {{
              "test-name": "Sample Test Name",
              "topic": "{topic}",
              "questions": [
                {{
                  "question": "Sample question text?",
                  "type": "single-answer",
                  "options": {{
                    "option1": "Answer A",
                    "option2": "Answer B",
                    "option3": "Answer C",
                    "option4": "Answer D"
                  }}
                }}
              ]
            }}
        """

    @staticmethod
    def build_open_question_prompt(topic, additional_prompt="", language="english"):
        return f"""
            Create 10-15 open-ended questions to assess someone's knowledge on "{topic}".
            {additional_prompt}

            Your entire response MUST be a valid JSON object.
            Generate the response in the following language: {language}.
            All user-visible string values (like test-name, topic, and question text) must be in {language}.
            Keep all JSON keys (like "test-name", "topic", "questions", "type") in English.

            Respond in this JSON format:

            {{
              "test-name": "Open Test",
              "topic": "{topic}",
              "questions": [
                {{
                  "question": "Explain how XYZ works...",
                  "type": "open-ended"
                }}
              ]
            }}
        """


class AnswerPromptBuilder:
    @staticmethod
    def build_batch_check_prompt(questions_and_answers, language="english"):
        """
        Builds a prompt to check all answers in a single API call.
        """
        qa_string = ""
        for i, qa in enumerate(questions_and_answers):
            qa_string += f"""
            {{
                "id": {i},
                "question": "{qa['question']}",
                "user_answer": "{qa['answer']}"
            }}
            """

        return f"""
            You are an expert evaluator. Below is a list of questions and the user's answers.
            For each question, reply with "correct" or "incorrect" and then provide a brief, one-sentence explanation for your reasoning in {language}.

            Evaluate the following items:
            {qa_string}

            Your entire response MUST be a valid JSON object.
            The JSON object should have a single key "assessments", which is an array.
            Each object in the array must contain the "id" of the question and the "assessment" string.
            The order of the assessments in the array MUST match the order of the questions provided.

            Example format:
            {{
                "assessments": [
                    {{
                        "id": 0,
                        "assessment": "correct. Your explanation was spot on."
                    }},
                    {{
                        "id": 1,
                        "assessment": "incorrect. This is actually caused by..."
                    }}
                ]
            }}
        """

    @staticmethod
    def build_check_prompt(question, answer, options, isopen, language="english"):
        if isopen:
            return (
                f'Reply with "correct" or "incorrect" in {language}. Then, briefly explain your reasoning in {language}.\n'
                f'Question: {question}\n'
                f'User\'s Answer: {answer}?\n'
            )
        else:
            return (
                f'Reply with "correct" or "incorrect" in {language}. Then, briefly explain your reasoning in {language}.\n'
                f'Question: {question}\n'
                f'Options: {str(options)}'
                f'User\'s Answer: {answer}?\n'
            )


class CoursePromptBuilder:
    @staticmethod
    def build_course_structure_prompt(topic, knowledge_assessment, assessed_answers, language="english", lesson_duration=15):
        assessed_answers_string = "\n".join([
            f"Q: {item['question']}\nA: {item['answer']}\nAssessment: {item['assessment']}\n"
            for item in assessed_answers
        ])

        return f"""
            A learner has completed a test on the topic: "{topic}".
            Here is a qualitative assessment of their knowledge based on the test:
            "{knowledge_assessment}"

            Below is a detailed breakdown of their responses:
            {assessed_answers_string}

            Your task:
            - Based on their performance and the overall assessment, design a personalized course outline to help them improve.
            - The course should include units. Each unit should contain lessons (with estimated completion time in minutes) and a test.
            - Do NOT generate lesson or test content yet—only the structure.
            - Lessons should be appropriately sequenced for progressive learning.
            - Your entire response MUST be a valid JSON object.
            - Generate the user-visible string values in the JSON (like course_title, unit_title, lesson_title, test_title) in the following language: {language}.
            - Keep all JSON keys (like "course_title", "units", "lessons", "estimated_time_minutes", "test", "test_title") in English.


            Return the course structure using the format:

            {{
              "course_title": "Personalized Course for {topic}",
              "units": [
                {{
                  "unit_title": "Unit 1: Foundations of {topic}",
                  "lessons": [
                    {{
                      "lesson_title": "Lesson 1.1: Basics of XYZ",
                      "estimated_time_minutes": {lesson_duration}
                    }}
                  ],
                  "test": {{
                    "test_title": "Unit 1 Assessment"
                  }}
                }}
              ]
            }}
        """


class LessonPromptBuilder:
    @staticmethod
    def build_lesson_content_prompt(lesson_title, unit_title, language="english", lesson_duration=15):
        return f"""
            You are an expert AI tutor.

            Generate a comprehensive, structured, and beginner-friendly lesson on the topic: "{lesson_title}".
            This lesson is part of the unit: "{unit_title}".
            The entire lesson content MUST be in {language}.

            Guidelines:
            - Use clear Markdown formatting (## Headings, bullet points, code blocks if needed).
            - Include step-by-step explanations, illustrative examples, and analogies.
            - The lesson's length MUST be calibrated for a {lesson_duration}-minute completion time for an average student. A shorter duration means a more concise, high-level overview. A longer duration allows for more depth, detail, and examples.
            - Use concise, easy-to-understand language for learners at various levels.

            Visual Aids:
            - Insert AI image placeholders only when the visual would enhance understanding.
            - All images must follow this format exactly:
              [IMAGE_PROMPT: "A grayscale, schematic-style diagram with no text, showing ..."]

            Example:
            [IMAGE_PROMPT: "A grayscale, schematic-style diagram with no text, showing the layers of a neural network"]

            IMPORTANT: Do NOT include any text in the images themselves, as the AI image generator struggles with rendering text in images. I want the images to be a grayscale, schematic diagram.

            The lesson should be clear, logically organized, and visually supported where appropriate.
        """