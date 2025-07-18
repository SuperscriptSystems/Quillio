from models.prompt_builders import AnswerPromptBuilder

class AnswerChecker:
    def __init__(self, model_func):
        self.ask_ai = model_func

    def check(self, question, answer,options, isopen):
        prompt = AnswerPromptBuilder.build_check_prompt(question, answer,options, isopen)
        return self.ask_ai(prompt).strip()
