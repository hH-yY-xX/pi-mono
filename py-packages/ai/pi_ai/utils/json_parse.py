"""
JSON parsing utilities for streaming responses.
"""

from __future__ import annotations

import json
from typing import Any, TypeVar

T = TypeVar("T")


def parse_streaming_json(partial_json: str | None) -> dict[str, Any]:
    """
    Attempts to parse potentially incomplete JSON during streaming.
    
    Always returns a valid object, even if the JSON is incomplete.
    
    Args:
        partial_json: The partial JSON string from streaming
    
    Returns:
        Parsed object or empty dict if parsing fails
    """
    if not partial_json or partial_json.strip() == "":
        return {}

    # Try standard parsing first (fastest for complete JSON)
    try:
        return json.loads(partial_json)
    except json.JSONDecodeError:
        pass

    # Try to recover partial JSON by closing brackets/braces
    try:
        # Count unclosed brackets and braces
        bracket_count = 0
        brace_count = 0
        in_string = False
        escape_next = False

        for char in partial_json:
            if escape_next:
                escape_next = False
                continue
            if char == "\\":
                escape_next = True
                continue
            if char == '"' and not escape_next:
                in_string = not in_string
                continue
            if in_string:
                continue
            if char == "[":
                bracket_count += 1
            elif char == "]":
                bracket_count -= 1
            elif char == "{":
                brace_count += 1
            elif char == "}":
                brace_count -= 1

        # Close any unclosed structures
        if in_string:
            partial_json += '"'
        partial_json += "]" * max(0, bracket_count)
        partial_json += "}" * max(0, brace_count)

        return json.loads(partial_json)
    except (json.JSONDecodeError, Exception):
        return {}
