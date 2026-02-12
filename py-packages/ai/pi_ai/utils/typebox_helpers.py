"""
TypeBox-style helper functions for JSON Schema generation.
"""

from __future__ import annotations

from typing import Any


def StringEnum(
    values: list[str],
    *,
    description: str | None = None,
    default: str | None = None,
) -> dict[str, Any]:
    """
    Creates a string enum schema compatible with multiple LLM providers.
    
    Args:
        values: List of allowed string values
        description: Optional description for the schema
        default: Optional default value
    
    Returns:
        JSON Schema dict for the enum
    
    Example:
        >>> OperationSchema = StringEnum(
        ...     ["add", "subtract", "multiply", "divide"],
        ...     description="The operation to perform"
        ... )
    """
    schema: dict[str, Any] = {
        "type": "string",
        "enum": values,
    }
    if description:
        schema["description"] = description
    if default:
        schema["default"] = default
    return schema
