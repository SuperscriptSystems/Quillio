import os
import json
import requests
import google.generativeai as genai

# --- OpenAI API Configuration ---
OPENAI_API_KEY = os.environ.get("API_KEY_OPENAI")
OPENAI_API_URL = "https://api.openai.com/v1/chat/completions"

# --- Gemini API Configuration ---
try:
    GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
    if not GEMINI_API_KEY:
        print("Warning: GEMINI_API_KEY environment variable is not set. Test generation will fail.")
    else:
        genai.configure(api_key=GEMINI_API_KEY)
except Exception as e:
    print(f"An error occurred during Gemini configuration: {e}")
    GEMINI_API_KEY = None

def ask_openai(prompt, model="gpt-4o-mini", json_mode=False):
    """
    Sends a prompt to the OpenAI Chat API and returns the text response.
    """
    if not OPENAI_API_KEY:
        return "Configuration Error: API_KEY_OPENAI is not set."

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
        response = requests.post(OPENAI_API_URL, headers=headers, data=json.dumps(data))
        response.raise_for_status()  # Will raise an exception for 4XX/5XX status codes
        result = response.json()
        content = result['choices'][0]['message']['content']
        print("Received response from OpenAI model.")
        return content
    except Exception as e:
        print(f"Error with OpenAI Chat model: {e}")
        return f"Error: {e}"

def ask_gemini(prompt, json_mode=False):
    """
    Sends a prompt to the Google Gemini API (1.5 Flash) and returns the text response.
    """
    if not GEMINI_API_KEY:
        return "Configuration Error: GEMINI_API_KEY is not set."

    model_instance = genai.GenerativeModel('gemini-1.5-flash-latest')
    generation_config = genai.types.GenerationConfig(
        response_mime_type="application/json"
    ) if json_mode else None

    try:
        print("Sending request to Gemini model: gemini-1.5-flash-latest...")
        response = model_instance.generate_content(prompt, generation_config=generation_config)
        content = response.text
        print("Received response from Gemini model.")
        return content
    except Exception as e:
        print(f"Error with Gemini model: {e}")
        return f"Error communicating with AI model: {e}"