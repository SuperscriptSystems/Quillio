import json


class TestPromptBuilder:
    @staticmethod
    def build_multiple_choice_prompt(topic, additional_context="", language="english", number_of_questions=5,
                                     user_profile=None, lesson_content_context=""):
        user_context_string = ""
        if user_profile:
            if user_profile.get('age'):
                user_context_string += f" The user is {user_profile.get('age')} years old."
            if user_profile.get('bio'):
                user_context_string += f" The user's bio: '{user_profile.get('bio')}'."
            if user_context_string:
                user_context_string = f"Consider the following user profile when creating questions:{user_context_string}"

        lesson_context_string = ""
        if lesson_content_context:
            lesson_context_string = f"""
            IMPORTANT: The following is the content of the lessons from this unit. You MUST base your questions directly on this material.
            --- LESSON CONTENT START ---
            {lesson_content_context}
            --- LESSON CONTENT END ---
            """

        return f"""
            You are creating a test on the topic: {topic}.
            {additional_context}
            {user_context_string}
            {lesson_context_string}

            Create {number_of_questions} multiple choice questions.

            IMPORTANT CONSTRAINTS:
            - Each question must have EXACTLY ONE correct answer
            - Do NOT create questions where multiple options are correct (e.g., "Which of the following are true: 1,2,4")
            - Do NOT create questions asking to "select all that apply"
            - Each question should have 4 options with only 1 being correct
            - Make sure the incorrect options are plausible but clearly wrong
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
    def build_course_structure_prompt(topic, knowledge_assessment, assessed_answers, language="english",
                                      lesson_duration=15, user_profile=None):
        assessed_answers_string = "\n".join([
            f"Q: {item['question']}\nA: {item['answer']}\nAssessment: {item['assessment']}\n"
            for item in assessed_answers
        ])

        user_context_string = ""
        if user_profile:
            profile_details = []
            if user_profile.get('age'):
                profile_details.append(f"Age: {user_profile.get('age')}")
            if user_profile.get('bio'):
                profile_details.append(f"Bio: '{user_profile.get('bio')}'")
            if profile_details:
                user_context_string = f"- Personalize the course for the following user profile: {'; '.join(profile_details)}."

        return f"""
            A learner has completed a test on the topic: "{topic}".
            Here is a qualitative assessment of their knowledge based on the test:
            "{knowledge_assessment}"

            Below is a detailed breakdown of their responses:
            {assessed_answers_string}

            Your task:
            - Based on their performance and the overall assessment, design a personalized course outline to help them improve.
            {user_context_string}
            - The course should include units. Each unit should contain lessons (with estimated completion time in minutes) and a test.
            - Do NOT generate lesson or test content yet—only the structure.
            - Lessons should be appropriately sequenced for progressive learning.
            - Your entire response MUST be a valid JSON object.
            - Generate the user-visible string values in the JSON (like course_title, unit_title, lesson_title, test_title) in the following language: {language}.
            - Keep all JSON keys (like "course_title", "units", "lessons", "estimated_time_minutes", "test", "test_title") in English.


            Return the course structure using the format:

            {{
              "course_title": "{topic}",
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


class ChatPromptBuilder:
    @staticmethod
    def build_tutor_prompt(lesson_content, unit_title, chat_history, user_question, 
                          language="english", course_structure=None, current_lesson_title=None):
        # Format the chat history for the prompt
        history_string = "\n".join([f"{msg['role']}: {msg['content']}" for msg in chat_history])
        
        course_context = ""
        if course_structure:
            # Build a structured overview of the course
            course_title = course_structure.get('course_title', 'this course')
            units = course_structure.get('units', [])
            
            # Find the current unit and its lessons
            current_unit = None
            for unit in units:
                if unit.get('unit_title') == unit_title:
                    current_unit = unit
                    break
            
            # Build course context
            course_context = f"## COURSE CONTEXT\n"
            course_context += f"You are helping a student with the course: **{course_title}**\n\n"
            
            if current_unit:
                lessons = current_unit.get('lessons', [])
                current_lesson_index = next((i for i, l in enumerate(lessons) 
                                          if l.get('lesson_title') == current_lesson_title), -1)
                
                course_context += f"### Current Unit: {unit_title}\n"
                
                # Show previous, current, and next lessons for context
                if current_lesson_index >= 0:
                    # Previous lessons
                    if current_lesson_index > 0:
                        prev_lesson = lessons[current_lesson_index - 1]
                        course_context += f"- Previous lesson: {prev_lesson.get('lesson_title')}\n"
                    
                    # Current lesson
                    course_context += f"- **Current lesson: {current_lesson_title}**\n"
                    
                    # Next lessons
                    if current_lesson_index < len(lessons) - 1:
                        next_lesson = lessons[current_lesson_index + 1]
                        course_context += f"- Next lesson: {next_lesson.get('lesson_title')}\n"
                
                course_context += "\n"
                
                # Add learning progression tips
                if current_lesson_index >= 0:
                    course_context += "### Learning Progression Tips\n"
                    if current_lesson_index > 0:
                        course_context += "- Consider how this concept builds on previous lessons\n"
                    if current_lesson_index < len(lessons) - 1:
                        course_context += "- Consider how this concept will be used in future lessons\n"
                    course_context += "- Maintain consistent terminology with the rest of the course\n"
                    course_context += "- Align the difficulty level with the student's progress\n"
            
            course_context += "\n"

        return f"""
        You are a friendly and encouraging AI tutor named Quillio.
        Your goal is to help a student understand the current lesson while being aware of their learning journey.
        
        {course_context}
        
        ## CURRENT LESSON CONTEXT
        - Unit: "{unit_title}"
        - Lesson: "{current_lesson_title or 'Current Lesson'}"
        
        ## LESSON CONTENT
        {lesson_content}
        
        ## CONVERSATION HISTORY
        {history_string}
        
        ## STUDENT'S QUESTION
        "{user_question}"
        
        ## INSTRUCTIONS
        1. First, analyze the student's question to understand what they're asking.
        2. If the question is related to the current lesson, provide a clear, concise answer.
        3. If the question is about a different topic in the course, connect it to what they've learned.
        4. If the question is off-topic, gently guide them back to the course material.
        5. Reference relevant parts of the lesson content in your response.
        6. Keep your response focused and educational.
        7. Use simple, clear language appropriate for the student's level.
        8. Respond in {language}.
        
        Now, provide a helpful response to the student's question.
        """.strip()


class CourseEditorPromptBuilder:
    @staticmethod
    def build_edit_prompt(current_course_json, user_request, language="english"):
        # Check if this is a title update request
        title_keywords = ["title", "name", "rename", "call this"]
        is_title_update = any(keyword in user_request.lower() for keyword in title_keywords)

        # If it's a title update, use the fast model for just the title
        if is_title_update and "course_title" in current_course_json:
            return {
                "course_title": user_request,
                "units": current_course_json.get("units", [])
            }

        course_str = json.dumps(current_course_json, indent=2)

        return f"""
        You are an expert AI curriculum editor. Your task is to modify a course structure, which is provided as a JSON object.
        The user will give you a command in plain text. You must interpret this command and apply it to the JSON structure.

        IMPORTANT RULES:
        1. Your entire response MUST be only the new, complete, and valid JSON object for the entire course.
        2. Do NOT add any extra text, explanations, or markdown formatting around the JSON.
        3. The structure of the JSON (keys like "course_title", "units", "lessons", "test") must be preserved.
        4. If you add new lessons, ensure they have an "estimated_time_minutes" key.
        5. All user-visible strings in the JSON (titles) must be in the following language: {language}.

        Here is the current course structure:
        {course_str}

        Here is the user's request:
        "{user_request}"

        Now, return the complete, modified JSON object reflecting the user's request.
        """

    @staticmethod
    def build_title_improvement_prompt(current_title, language="english"):
        """Generate a prompt to improve the course title."""
        return f"""
        You are an expert at creating engaging and concise course titles. 
        
        Your task is to take the current course title and improve it to be more engaging and concise.
        
        Current title: "{current_title}"
        
        RULES:
        1. Respond with ONLY the improved title, nothing else
        2. Keep it under 10 words
        3. Make it engaging and professional
        4. Do not use markdown, quotes, or any formatting
        5. Do not include any explanations or additional text
        6. The title should be in {language}
        
        Improved title: """


class LessonPromptBuilder:
    @staticmethod
    def build_lesson_content_prompt(lesson_title, unit_title, language="english", lesson_duration=15, user_profile=None,
                                    course_structure=None, current_lesson_index=None, total_lessons=None):
        user_context_string = ""
        if user_profile:
            profile_details = []
            if user_profile.get('age'):
                profile_details.append(f"Age: {user_profile.get('age')}")
            if user_profile.get('bio'):
                profile_details.append(f"Bio: '{user_profile.get('bio')}'")  # noqa: B907
            if profile_details:
                user_context_string = f"- Personalize the tone, examples, and analogies for the user. User profile: {'; '.join(profile_details)}. For instance, if their bio mentions programming, use technical analogies."

        course_context_string = ""
        if course_structure:
            # Extract relevant course structure information
            course_title = course_structure.get('course_title', '')
            units = course_structure.get('units', [])
            
            # Build course structure context
            course_overview = f"Course: {course_title}\n\n"
            
            for unit in units:
                unit_title_display = unit.get('unit_title', 'Untitled Unit')
                course_overview += f"- {unit_title_display}\n"
                
                lessons = unit.get('lessons', [])
                for i, lesson in enumerate(lessons, 1):
                    lesson_title_display = lesson.get('lesson_title', 'Untitled Lesson')
                    is_current = (lesson_title_display == lesson_title and unit_title_display == unit_title)
                    prefix = "→ " if is_current else "  "
                    course_overview += f"  {prefix}Lesson {i}: {lesson_title_display}\n"
            
            # Add learning progression context
            progression_context = ""
            if current_lesson_index is not None and total_lessons:
                progression_context = (
                    f"This is lesson {current_lesson_index} of {total_lessons} in the course. "
                    f"You are {int((current_lesson_index/total_lessons)*100)}% through the course.\n\n"
                )
            
            course_context_string = f"""
            ## COURSE CONTEXT
            {progression_context}
            This lesson is part of the following course structure:
            ```
            {course_overview}
            ```
            
            When creating this lesson, please:
            1. Reference and build upon concepts from previous lessons when appropriate
            2. Set up concepts that will be explored in future lessons
            3. Maintain consistent terminology and difficulty level throughout the course
            4. Ensure the content fits within the overall learning progression
            """.format(progression_context=progression_context, course_overview=course_overview)

        return f"""
            You are an expert AI tutor creating a lesson for an online learning platform.

            ## TASK
            Generate a comprehensive, structured, and beginner-friendly lesson on the topic: "{lesson_title}"
            This lesson is part of the unit: "{unit_title}"
            The entire lesson content MUST be in {language}.
            
            {course_context_string}
            
            ## GUIDELINES
            - Use clear Markdown formatting (## Headers, bullet points, code blocks if needed).
            - Include step-by-step explanations, illustrative examples, and analogies.
            - The lesson's length MUST be calibrated for a {lesson_duration}-minute completion time.
            - Use concise, easy-to-understand language for learners at various levels.
            {user_context_string}

            Mathematical Formulas:
            - For inline mathematical expressions, wrap them in single dollar signs, like `$\frac{1}{2}$`.
            - For display-style equations (on their own line), wrap them in double dollar signs, like `$$\sum_{{i=1}}^{{n}} i = \frac{{n(n + 1)}}{{2}}$$`.
            - Use standard LaTeX syntax for all mathematical formulas.

            Visual Aids:
            - Insert AI image placeholders only when the visual would enhance understanding.
            - All images must follow this format exactly:
              [IMAGE_PROMPT: "A grayscale, schematic-style diagram with no text, showing ..."]

            Example:
            [IMAGE_PROMPT: "A grayscale, schematic-style diagram with no text, showing the layers of a neural network"]

            IMPORTANT: Do NOT include any text in the images themselves, as the AI image generator struggles with rendering text in images. I want the images to be a grayscale, schematic diagram.

            The lesson should be clear, logically organized, and visually supported where appropriate.
        """