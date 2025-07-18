class TestPromptBuilder:
    @staticmethod
    def build_multiple_choice_prompt(topic, additional_prompt=""):
        return f"""
            You are assessing a person's skill level in this topic: {topic}.
            {additional_prompt}

            Create 10-15 multiple choice questions in this format (valid JSON only):

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
    def build_open_question_prompt(topic, additional_prompt=""):
        return f"""
            Create 10-15 open-ended questions to assess someone's knowledge on "{topic}".
            {additional_prompt}

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
    def build_check_prompt(question, answer, options, isopen):
        if isopen:
            return (
                'Reply: "correct" or "incorrect". Explain your reasoning.\n'
                f'Here is a question: {question}\n'
                f'Do you think this answer is correct: {answer}?\n'
            )
        elif not isopen:
            return (
                'Reply: "correct" or "incorrect". Explain your reasoning.\n'
                f'Here is a question: {question}\n'
                f'Here are the options: {str(options)}'
                f'Do you think this answer is correct: {answer}?\n'
            )


class CoursePromptBuilder:
    @staticmethod
    def build_course_structure_prompt(topic, final_score, assessed_answers, lesson_duration=15):
        assessed_answers_string = "\n".join([
            f"Q: {item['question']}\nA: {item['answer']}\nAssessment: {item['assessment']}\n"
            for item in assessed_answers
        ])

        return f"""
            A learner has completed a test on the topic: "{topic}" and scored {final_score}%.
            Below is an assessment of their responses:

            {assessed_answers_string}

            Your task:
            - Based on their performance, design a personalized course outline to help them improve.
            - The course should include units. Each unit should contain lessons (with estimated completion time in minutes) and a test.
            - Do NOT generate lesson or test content yet—only the structure.
            - Lessons should be appropriately sequenced for progressive learning.

            Return the course structure as a valid JSON object using the format:

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
    def build_lesson_content_prompt(lesson_title, unit_title, lesson_duration=15):
        return f"""
            You are an expert AI tutor.

            Generate a comprehensive, structured, and beginner-friendly lesson on the topic: "{lesson_title}".
            This lesson is part of the unit: "{unit_title}".

            Guidelines:
            - Use clear Markdown formatting (## Headings, bullet points, code blocks if needed).
            - Include step-by-step explanations, illustrative examples, and analogies.
            - The content should be suitable for a {lesson_duration}-minute self-paced lesson.
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
