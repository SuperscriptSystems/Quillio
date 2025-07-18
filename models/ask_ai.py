import json
import requests
import os

OPENAI_API_KEY = os.environ.get("API_KEY_OPENAI")


def ask_ai(prompt, model="gpt-4.1-mini", url="https://api.openai.com/v1/chat/completions"):
    headers = {
        'Content-Type': 'application/json',
        'Authorization': f'Bearer {OPENAI_API_KEY}'
    }

    data = {
        'model': model,
        'messages': [{'role': 'user', 'content': prompt}],
        'max_tokens': 3000,  # Increased for longer lessons
        'temperature': 0.7,
        'stream': False
    }

    try:
        print(f"Sending request to OpenAI Chat model...")
        response = requests.post(url, headers=headers, data=json.dumps(data))

        if response.status_code != 200:
            raise Exception(f"OpenAI API responded with status code {response.status_code}: {response.text}")

        result = response.json()
        content = result['choices'][0]['message']['content']
        print("Received response from Chat model.")
        return content

    except Exception as e:
        print(f"Error with OpenAI Chat model: {e}")
        return None


def generate_image_from_prompt(prompt, model="dall-e-3", url="https://api.openai.com/v1/images/generations"):
    headers = {
        'Content-Type': 'application/json',
        'Authorization': f'Bearer {OPENAI_API_KEY}'
    }

    data = {
        'model': model,
        'prompt': prompt,
        'n': 1,  # Generate one image
        'size': "1024x1024"  # Define the size of the image
    }

    try:
        print(f"Sending request to DALL-E model for prompt: {prompt}")
        response = requests.post(url, headers=headers, data=json.dumps(data))

        if response.status_code != 200:
            raise Exception(f"OpenAI Image API responded with status code {response.status_code}: {response.text}")

        result = response.json()
        image_url = result['data'][0]['url']
        print(f"Received image URL: {image_url}")
        return image_url

    except Exception as e:
        print(f"Error with OpenAI Image model: {e}")
        return None