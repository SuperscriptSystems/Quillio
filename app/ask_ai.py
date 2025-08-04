import os
import json
import requests

OPENAI_API_KEY = os.environ.get("API_KEY_OPENAI")
API_URL = "https://api.openai.com/v1/chat/completions"

def ask_ai(prompt, model="gpt-4o-mini", json_mode=False):
    """
    Sends a prompt to the OpenAI Chat API and returns the text response.
    Switches between gpt-4o-mini for fast tasks and gpt-4o for complex generation.
    """
    if not OPENAI_API_KEY:
        print("Error: API_KEY_OPENAI environment variable is not set.")
        return "Configuration Error: The server's OpenAI API key is not set."

    headers = {
        'Content-Type': 'application/json',
        'Authorization': f'Bearer {OPENAI_API_KEY}'
    }

    data = {
        'model': model,
        'messages': [{'role': 'user', 'content': prompt}],
        'max_tokens': 4000,
        'temperature': 0.7,
    }

    if json_mode:
        data['response_format'] = {'type': 'json_object'}

    try:
        print(f"Sending request to OpenAI model: {model}...")
        response = requests.post(API_URL, headers=headers, data=json.dumps(data))

        if response.status_code != 200:
            raise Exception(f"OpenAI API responded with status code {response.status_code}: {response.text}")

        result = response.json()
        content = result['choices'][0]['message']['content']
        print("Received response from OpenAI model.")
        return content

    except Exception as e:
        print(f"Error with OpenAI Chat model: {e}")
        return f"Error: {e}"