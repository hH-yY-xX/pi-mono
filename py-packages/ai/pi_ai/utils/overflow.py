"""
Context overflow detection utilities.
"""

from __future__ import annotations

import re

from pi_ai.types import AssistantMessage

# Regex patterns to detect context overflow errors from different providers
OVERFLOW_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"prompt is too long", re.IGNORECASE),  # Anthropic
    re.compile(r"input is too long for requested model", re.IGNORECASE),  # Amazon Bedrock
    re.compile(r"exceeds the context window", re.IGNORECASE),  # OpenAI
    re.compile(r"input token count.*exceeds the maximum", re.IGNORECASE),  # Google
    re.compile(r"maximum prompt length is \d+", re.IGNORECASE),  # xAI
    re.compile(r"reduce the length of the messages", re.IGNORECASE),  # Groq
    re.compile(r"maximum context length is \d+ tokens", re.IGNORECASE),  # OpenRouter
    re.compile(r"exceeds the limit of \d+", re.IGNORECASE),  # GitHub Copilot
    re.compile(r"exceeds the available context size", re.IGNORECASE),  # llama.cpp
    re.compile(r"greater than the context length", re.IGNORECASE),  # LM Studio
    re.compile(r"context window exceeds limit", re.IGNORECASE),  # MiniMax
    re.compile(r"exceeded model token limit", re.IGNORECASE),  # Kimi For Coding
    re.compile(r"context[_ ]length[_ ]exceeded", re.IGNORECASE),  # Generic
    re.compile(r"too many tokens", re.IGNORECASE),  # Generic
    re.compile(r"token limit exceeded", re.IGNORECASE),  # Generic
]


def is_context_overflow(message: AssistantMessage, context_window: int | None = None) -> bool:
    """
    Check if an assistant message represents a context overflow error.
    
    This handles two cases:
    1. Error-based overflow: Most providers return stop_reason "error" with a
       specific error message pattern.
    2. Silent overflow: Some providers accept overflow requests and return
       successfully. For these, we check if usage.input exceeds the context window.
    
    Args:
        message: The assistant message to check
        context_window: Optional context window size for detecting silent overflow
    
    Returns:
        True if the message indicates a context overflow
    """
    # Case 1: Check error message patterns
    if message.stop_reason == "error" and message.error_message:
        # Check known patterns
        if any(p.search(message.error_message) for p in OVERFLOW_PATTERNS):
            return True

        # Cerebras and Mistral return 400/413 with no body
        if re.match(r"^4(00|13)\s*(status code)?\s*\(no body\)", message.error_message, re.IGNORECASE):
            return True

    # Case 2: Silent overflow - successful but usage exceeds context
    if context_window and message.stop_reason == "stop":
        input_tokens = message.usage.input + message.usage.cache_read
        if input_tokens > context_window:
            return True

    return False


def get_overflow_patterns() -> list[re.Pattern[str]]:
    """Get the overflow patterns for testing purposes."""
    return OVERFLOW_PATTERNS.copy()
