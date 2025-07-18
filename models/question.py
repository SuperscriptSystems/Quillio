class Question:
    def __init__(self, test_id=1, question="", options=None):
        self.test_id=test_id
        self.question = question
        self.options = options or {}
