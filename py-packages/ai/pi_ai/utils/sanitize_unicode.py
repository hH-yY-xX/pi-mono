"""
Unicode sanitization utilities.
"""

from __future__ import annotations


def sanitize_surrogates(text: str) -> str:
    """
    Remove surrogate characters from text.
    
    Surrogate characters (U+D800 to U+DFFF) are invalid in UTF-8 and can
    cause issues with various APIs. This function replaces them with the
    Unicode replacement character.
    
    Args:
        text: The text to sanitize
    
    Returns:
        The sanitized text
    """
    return text.encode("utf-8", errors="replace").decode("utf-8")
