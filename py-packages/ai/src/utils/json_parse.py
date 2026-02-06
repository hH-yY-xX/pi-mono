"""
JSON parsing utilities for streaming responses.
"""

import json
from typing import Any, Optional

def parse_streaming_json(partial_json: str) -> Optional[Any]:
    """
    Parse partial JSON string that may be incomplete.
    
    Args:
        partial_json: Partial JSON string
        
    Returns:
        Parsed JSON object or None if parsing fails
    """
    if not partial_json:
        return None
        
    try:
        # Try to parse complete JSON first
        return json.loads(partial_json)
    except json.JSONDecodeError:
        # If that fails, try to parse incrementally
        try:
            # Remove trailing incomplete tokens
            cleaned = partial_json.rstrip()
            if cleaned.endswith(','):
                cleaned = cleaned[:-1]
            if cleaned.endswith(':'):
                cleaned = cleaned[:-1]
                
            # Try to close open structures
            brace_count = cleaned.count('{') - cleaned.count('}')
            bracket_count = cleaned.count('[') - cleaned.count(']')
            
            # Add closing brackets/braces if needed
            if brace_count > 0:
                cleaned += '}' * brace_count
            if bracket_count > 0:
                cleaned += ']' * bracket_count
                
            return json.loads(cleaned)
        except json.JSONDecodeError:
            # If still can't parse, return None
            return None

def validate_json_structure(obj: Any) -> bool:
    """
    Validate that a parsed JSON object has valid structure.
    
    Args:
        obj: Parsed JSON object
        
    Returns:
        True if structure is valid
    """
    if obj is None:
        return False
        
    if isinstance(obj, dict):
        # Check that all keys are strings
        return all(isinstance(k, str) for k in obj.keys())
    elif isinstance(obj, list):
        # Lists are always valid
        return True
    else:
        # Primitive types are valid
        return isinstance(obj, (str, int, float, bool))