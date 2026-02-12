"""
Tool validation utilities.
"""

from __future__ import annotations

import json
from copy import deepcopy
from typing import Any

from pi_ai.types import Tool, ToolCall

# Try to use jsonschema for validation if available
try:
    import jsonschema
    from jsonschema import Draft7Validator

    _HAS_JSONSCHEMA = True
except ImportError:
    _HAS_JSONSCHEMA = False


def validate_tool_call(tools: list[Tool], tool_call: ToolCall) -> Any:
    """
    Finds a tool by name and validates the tool call arguments against its schema.
    
    Args:
        tools: Array of tool definitions
        tool_call: The tool call from the LLM
    
    Returns:
        The validated arguments
    
    Raises:
        ValueError: If tool is not found or validation fails
    """
    tool = next((t for t in tools if t.name == tool_call.name), None)
    if not tool:
        raise ValueError(f'Tool "{tool_call.name}" not found')
    return validate_tool_arguments(tool, tool_call)


def validate_tool_arguments(tool: Tool, tool_call: ToolCall) -> Any:
    """
    Validates tool call arguments against the tool's JSON schema.
    
    Args:
        tool: The tool definition with JSON schema
        tool_call: The tool call from the LLM
    
    Returns:
        The validated (and potentially coerced) arguments
    
    Raises:
        ValueError: With formatted message if validation fails
    """
    # Skip validation if jsonschema is not available
    if not _HAS_JSONSCHEMA:
        return tool_call.arguments

    # Clone arguments so we can safely modify
    args = deepcopy(tool_call.arguments)

    try:
        validator = Draft7Validator(tool.parameters)
        errors = list(validator.iter_errors(args))

        if not errors:
            return args

        # Format validation errors nicely
        error_messages = []
        for err in errors:
            path = ".".join(str(p) for p in err.absolute_path) if err.absolute_path else "root"
            error_messages.append(f"  - {path}: {err.message}")

        error_str = "\n".join(error_messages)
        args_str = json.dumps(tool_call.arguments, indent=2)

        raise ValueError(
            f'Validation failed for tool "{tool_call.name}":\n{error_str}\n\n'
            f"Received arguments:\n{args_str}"
        )
    except jsonschema.exceptions.SchemaError as e:
        # Schema itself is invalid - return args as-is
        return args
