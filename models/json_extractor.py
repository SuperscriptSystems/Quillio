import json
import re

class JsonExtractor:
    @staticmethod
    def extract_json(raw_text):
        """
        Extract and parse JSON content from a raw string.
        Handles Markdown code blocks and various JSON formatting issues.
        """
        # First, try to extract JSON from code blocks
        json_string = JsonExtractor._strip_code_block(raw_text.strip())
        
        # If no code blocks found, try to use the raw text
        if not json_string or json_string == raw_text.strip():
            json_string = raw_text.strip()
            
        # Clean up common JSON formatting issues
        json_string = json_string.strip()
        
        # Remove markdown code block markers if they're still present
        if json_string.startswith('```'):
            json_string = re.sub(r'^```(?:json)?\s*|\s*```$', '', json_string, flags=re.DOTALL)
            
        # Remove any remaining backticks
        json_string = json_string.strip('`\n ')
        
        # Handle escaped characters properly
        try:
            # First try to parse as-is
            return json.loads(json_string)
        except json.JSONDecodeError as e:
            try:
                # Try to fix common issues
                # Remove any control characters except newlines and tabs
                json_string = re.sub(r'[\x00-\x1f\\]', lambda m: '\\u{:04x}'.format(ord(m.group(0))) if m.group(0) not in '\n\t' else m.group(0), json_string)
                
                # Try to find JSON object/array in the text
                json_match = re.search(r'({[\s\S]*})|(\[[\s\S]*\])', json_string)
                if json_match:
                    return json.loads(json_match.group(0))
                    
                # If we still can't parse, try to clean up the string more aggressively
                json_string = re.sub(r',\s*([}\]])', r'\1', json_string)  # Remove trailing commas
                json_string = re.sub(r'\\([^"\\/bfnrtu])', r'\\\\\1', json_string)  # Fix escaped characters
                
                # Try parsing again
                return json.loads(json_string)
                
            except Exception as inner_e:
                # If all else fails, try to manually extract and build the JSON
                try:
                    return JsonExtractor._manual_json_extract(raw_text)
                except Exception as manual_e:
                    raise ValueError(
                        f"JSON parse error: {e}\n"
                        f"Cleaned content:\n{json_string}\n\n"
                        f"Original content:\n{raw_text}\n\n"
                        f"Manual extraction also failed: {manual_e}"
                    )

    @staticmethod
    def _strip_code_block(text):
        """
        Remove Markdown code block markers from the raw text.
        Handles both ```json and regular code blocks.
        """
        # Try to find a JSON code block first
        match = re.search(r'```(?:json)?\s*({[\s\S]*?})\s*```', text)
        if match:
            return match.group(1)
            
        # If no JSON code block, try to find any code block
        match = re.search(r'```(?:[^`]*?\n)?([\s\S]*?)\s*```', text)
        if match:
            return match.group(1)
            
        # If no code blocks, try to find JSON object/array directly
        match = re.search(r'({[\s\S]*})|(\[[\s\S]*\])', text)
        return match.group(0) if match else text
        
    @staticmethod
    def _manual_json_extract(text):
        """
        Manually extract and build JSON when standard parsing fails.
        This is a fallback method for particularly problematic JSON.
        """
        # Try to find the main JSON object/array
        match = re.search(r'(?:{|\[)[\s\S]*(?:}|\])', text)
        if not match:
            raise ValueError("No JSON object or array found in text")
            
        json_str = match.group(0)
        
        # Fix common issues
        json_str = re.sub(r',\s*([}\]])(?!\s*[{\[]|$)', r'\1', json_str)  # Trailing commas
        json_str = re.sub(r'([{\[,]\s*)([a-zA-Z0-9_]+)(\s*:)'
                         r'(?=(?:[^"\']*["\'][^"\']*["\'])*[^"\']*$)', 
                         r'\1"\2"\3', json_str)  # Unquoted keys
        
        # Handle escaped quotes inside strings
        json_str = re.sub(r'([^\\])\\(["\'\\])', r'\1\\\\\2', json_str)
        
        # Parse the cleaned JSON
        return json.loads(json_str)
