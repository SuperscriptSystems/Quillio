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
    Sends a prompt to the OpenAI Chat API.
    Returns a tuple: (text_response, tokens_used)
    """
    if not OPENAI_API_KEY:
        return "Configuration Error: API_KEY_OPENAI is not set.", 0

    headers = {'Content-Type': 'application/json', 'Authorization': f'Bearer {OPENAI_API_KEY}'}
    data = {'model': model, 'messages': [{'role': 'user', 'content': prompt}], 'max_tokens': 4000, 'temperature': 0.7}
    if json_mode:
        data['response_format'] = {'type': 'json_object'}

    try:
        print(f"Sending request to OpenAI model: {model}...")
        response = requests.post(OPENAI_API_URL, headers=headers, data=json.dumps(data))
        response.raise_for_status()
        result = response.json()
        content = result['choices'][0]['message']['content']
        tokens = result.get('usage', {}).get('total_tokens', 0)
        print("Received response from OpenAI model.")
        return content, tokens
    except Exception as e:
        print(f"Error with OpenAI Chat model: {e}")
        return f"Error: {e}", 0

def ask_gemini(prompt, json_mode=False):
    """
    Sends a prompt to the Google Gemini API.
    Returns a tuple: (text_response, tokens_used)
    """
    if not GEMINI_API_KEY:
        return "Configuration Error: GEMINI_API_KEY is not set.", 0

    model_instance = genai.GenerativeModel("gemini-1.5-flash-latest")
    generation_config = genai.types.GenerationConfig(response_mime_type="application/json") if json_mode else None

    try:
        print("Sending request to Gemini model: gemini-1.5-flash-latest...")
        response = model_instance.generate_content(prompt, generation_config=generation_config)
        content = response.text
        tokens = response.usage_metadata.total_token_count if response.usage_metadata else 0
        print('Received response from Gemini model.')
        return content, tokens
    except Exception as e:
        print(f"Error with Gemini model: {e}")
        return f"Error communicating with AI model: {e}", 0

def ask_gemini_stream(prompt):
    """
    Sends a prompt to the Google Gemini API and streams the response.
    Yields text chunks as they are generated.
    """
    if not GEMINI_API_KEY:
        yield "Configuration Error: GEMINI_API_KEY is not set."
        return

    model_instance = genai.GenerativeModel("gemini-1.5-flash-latest")
    try:
        print("Sending streaming request to Gemini model: gemini-1.5-flash-latest...")
        response_stream = model_instance.generate_content(prompt, stream=True)
        for chunk in response_stream:
            if chunk.text:
                yield chunk.text
        print('Finished streaming response from Gemini model.')
    except Exception as e:
        print(f"Error with Gemini streaming model: {e}")
        yield f"Error communicating with AI model: {e}"