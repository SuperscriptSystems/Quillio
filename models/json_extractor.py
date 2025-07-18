import json
import re

class JsonExtractor:
    @staticmethod
    def extract_json(raw_text):
        """
        Extract and parse JSON content from a raw string.
        Supports Markdown-style code blocks (e.g., ```json ... ```).
        """
        json_string = JsonExtractor._strip_code_block(raw_text)

        try:
            return json.loads(json_string)
        except json.JSONDecodeError as e:
            raise ValueError(f"JSON parse error: {e}\nRaw content:\n{raw_text}")

    @staticmethod
    def _strip_code_block(text):
        """
        Remove Markdown code block markers from the raw text.
        """
        match = re.search(r"```(?:json)?\s*(.*?)\s*```", text, re.DOTALL)
        return match.group(1).strip() if match else text
