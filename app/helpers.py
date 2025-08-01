from models.fulltest import Test
from models.question import Question

def save_test_to_dict(test):
    """Serializes a Test object into a dictionary to be stored in the session."""
    questions = [{"question": q.question, "options": q.options} for q in test.questions]
    return {"test_name": test.test_name, "topic": test.topic, "questions": questions}

def load_test_from_dict(data):
    """Deserializes a dictionary from the session back into a Test object."""
    questions = [Question(question=q["question"], options=q["options"]) for q in data["questions"]]
    return Test(data["test_name"], data["topic"], questions)

def render_answer_input(question):
    """Generates the HTML for multiple-choice radio buttons."""
    html = ""
    for option in question.options.values():
        html += f'<label><input type="radio" name="answer" value="{option}" required> <span>{option}</span></label><br>'
    return html