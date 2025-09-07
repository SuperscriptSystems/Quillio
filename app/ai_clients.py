import os
import requests
from typing import Generator, Tuple, Optional

# OpenRouter configuration
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"

# Model configurations
MODEL_CONFIGS = {
    "gemini-1.5-flash": {
        "model": "google/gemini-flash-1.5",
        "max_output_tokens": 4000,
        "temperature": 0.7,
        "top_p": 1.0
    },
    "gemini-1.5-pro": {
        "model": "google/gemini-pro-1.5",
        "max_output_tokens": 4000,
        "temperature": 0.7,
        "top_p": 1.0
    }
}


def _call_openrouter(prompt: str, model_name: str = "gemini-1.5-flash", json_mode: bool = False) -> Tuple[str, int]:
    """
    Internal function to call OpenRouter with the specified model.
    Returns a tuple: (text_response, tokens_used)
    """
    try:
        config = MODEL_CONFIGS.get(model_name, MODEL_CONFIGS["gemini-1.5-flash"])

        if json_mode:
            prompt = f"""You are a helpful assistant that responds in JSON format. 
            Ensure your response can be parsed by json.loads().
            Here's the request: {prompt}"""

        headers = {
            "Authorization": f"Bearer {OPENROUTER_API_KEY}",
            "Content-Type": "application/json",
        }

        payload = {
            "model": config["model"],
            "messages": [{"role": "user", "content": prompt}],
            "temperature": config["temperature"],
            "top_p": config["top_p"],
            "max_tokens": config["max_output_tokens"]
        }

        response = requests.post(OPENROUTER_URL, headers=headers, json=payload)
        response.raise_for_status()
        data = response.json()

        text_response = data["choices"][0]["message"]["content"]

        tokens_used = data.get("usage", {}).get("total_tokens", len(text_response) // 4)

        return text_response, tokens_used

    except Exception as e:
        print(f"Error with OpenRouter API: {str(e)}")
        raise


def _stream_openrouter(prompt: str, model_name: str = "gemini-1.5-flash") -> Generator[str, None, None]:
    """
    Stream response from OpenRouter API.
    Yields text chunks as they are generated.
    """
    import sseclient

    try:
        config = MODEL_CONFIGS.get(model_name, MODEL_CONFIGS["gemini-1.5-flash"])

        headers = {
            "Authorization": f"Bearer {OPENROUTER_API_KEY}",
            "Content-Type": "application/json",
        }

        payload = {
            "model": config["model"],
            "messages": [{"role": "user", "content": prompt}],
            "temperature": config["temperature"],
            "top_p": config["top_p"],
            "max_tokens": config["max_output_tokens"],
            "stream": True,
        }

        response = requests.post(OPENROUTER_URL, headers=headers, json=payload, stream=True)
        response.raise_for_status()

        client = sseclient.SSEClient(response)

        for event in client.events():
            if event.data == "[DONE]":
                break
            try:
                chunk = eval(event.data)  # safe enough since OpenRouter returns JSON
                delta = chunk.get("choices", [{}])[0].get("delta", {}).get("content", "")
                if delta:
                    yield delta
            except Exception:
                continue

    except Exception as e:
        print(f"Error with OpenRouter API streaming: {str(e)}")
        raise


# Public API functions
def ask_ai(prompt: str, model: str = "gemini-1.5-flash", json_mode: bool = False) -> Tuple[str, int]:
    """
    Sends a prompt to the specified OpenRouter model.
    Returns a tuple: (text_response, estimated_tokens_used)
    """
    return _call_openrouter(prompt, model, json_mode)


def ask_ai_stream(prompt: str, model: str = "gemini-1.5-flash") -> Generator[str, None, None]:
    """
    Sends a prompt to the specified OpenRouter model and streams the response.
    Yields text chunks as they are generated.
    """
    return _stream_openrouter(prompt, model)


# Backward compatibility
def ask_gemini(prompt: str, json_mode: bool = False) -> Tuple[str, int]:
    return ask_ai(prompt, "gemini-1.5-flash", json_mode)


def ask_gemini_stream(prompt: str) -> Generator[str, None, None]:
    return ask_ai_stream(prompt, "gemini-1.5-flash")
