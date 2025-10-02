import os
import google.generativeai as genai
from typing import Generator, Tuple, Optional, List

# Configure Gemini API
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

def list_available_models() -> List[str]:
    """List all available models from the API."""
    try:
        models = genai.list_models()
        return [model.name for model in models]
    except Exception as e:
        print(f"Error listing models: {e}")
        return []

# Get available models and use the first suitable one
available_models = list_available_models()
print("Available models:", available_models)

# Use gemini-2.5-flash as the default model
DEFAULT_MODEL = "gemini-2.5-flash"
print(f"Using model: {DEFAULT_MODEL}")

# Model configurations
MODEL_CONFIGS = {
    "gemini-2.5-flash": {
        "model": "gemini-2.5-flash",
        "max_output_tokens": 8192,  # Higher token limit for better context
        "temperature": 0.7,
        "top_p": 1.0,
        "top_k": 40
    },
    "gemini-2.5-pro": {
        "model": "gemini-2.5-pro",
        "max_output_tokens": 8192,
        "temperature": 0.7,
        "top_p": 1.0,
        "top_k": 40
    }
}

def _call_gemini(prompt: str, model_name: str = None, json_mode: bool = False) -> Tuple[str, int]:
    """
    Internal function to call Gemini API with the specified model.
    Returns a tuple: (text_response, tokens_used)
    """
    try:
        model_name = model_name or DEFAULT_MODEL
        config = MODEL_CONFIGS.get(model_name, next(iter(MODEL_CONFIGS.values())))
        
        model = genai.GenerativeModel(
            model_name=config["model"],
            generation_config={
                "temperature": config["temperature"],
                "top_p": config["top_p"],
                "top_k": config["top_k"],
                "max_output_tokens": config["max_output_tokens"],
            },
        )
        
        if json_mode:
            prompt = f"""You are a helpful assistant that responds in JSON format. 
            Ensure your response can be parsed by json.loads().
            Here's the request: {prompt}"""
        
        response = model.generate_content(prompt)
        
        if not response.text:
            raise ValueError("No response text from Gemini API")
            
        # Estimate token usage (Gemini doesn't return token count in response)
        # Rough estimate: 1 token ~= 4 chars in English
        tokens_used = len(response.text) // 4
        
        return response.text, tokens_used
        
    except Exception as e:
        print(f"Error with Gemini API: {str(e)}")
        raise

def _stream_gemini(prompt: str, model_name: str = None) -> Generator[str, None, None]:
    """
    Stream response from Gemini API.
    Yields text chunks as they are generated.
    """
    try:
        model_name = model_name or DEFAULT_MODEL
        config = MODEL_CONFIGS.get(model_name, next(iter(MODEL_CONFIGS.values())))
        
        model = genai.GenerativeModel(
            model_name=config["model"],
            generation_config={
                "temperature": config["temperature"],
                "top_p": config["top_p"],
                "top_k": config["top_k"],
                "max_output_tokens": config["max_output_tokens"],
            },
        )
        
        response = model.generate_content(prompt, stream=True)
        
        for chunk in response:
            if chunk.text:
                yield chunk.text
                
    except Exception as e:
        print(f"Error with Gemini API streaming: {str(e)}")
        raise

# Public API functions
def ask_ai(prompt: str, model: str = None, json_mode: bool = False) -> Tuple[str, int]:
    """
    Sends a prompt to the specified Gemini model.
    Returns a tuple: (text_response, estimated_tokens_used)
    """
    return _call_gemini(prompt, model, json_mode)

def ask_ai_stream(prompt: str, model: str = None) -> Generator[str, None, None]:
    """
    Sends a prompt to the specified Gemini model and streams the response.
    Yields text chunks as they are generated.
    """
    yield from _stream_gemini(prompt, model)

# Backward compatibility
def ask_gemini(prompt: str, json_mode: bool = False) -> Tuple[str, int]:
    return ask_ai(prompt, None, json_mode)

def ask_gemini_stream(prompt: str) -> Generator[str, None, None]:
    return ask_ai_stream(prompt, None)