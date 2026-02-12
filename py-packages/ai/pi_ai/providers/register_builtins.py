"""
Register built-in API providers.
"""

from __future__ import annotations

from pi_ai.api_registry import ApiProvider, clear_api_providers, register_api_provider
from pi_ai.providers.anthropic import stream_anthropic, stream_simple_anthropic
from pi_ai.providers.openai_completions import (
    stream_openai_completions,
    stream_simple_openai_completions,
)


def register_builtin_api_providers() -> None:
    """Register all built-in API providers."""
    register_api_provider(
        ApiProvider(
            api="anthropic-messages",
            stream=stream_anthropic,
            stream_simple=stream_simple_anthropic,
        )
    )

    register_api_provider(
        ApiProvider(
            api="openai-completions",
            stream=stream_openai_completions,
            stream_simple=stream_simple_openai_completions,
        )
    )

    # TODO: Add other providers as needed
    # - openai-responses
    # - azure-openai-responses
    # - openai-codex-responses
    # - google-generative-ai
    # - google-gemini-cli
    # - google-vertex
    # - bedrock-converse-stream


def reset_api_providers() -> None:
    """Clear and re-register all built-in API providers."""
    clear_api_providers()
    register_builtin_api_providers()


# Auto-register on import
register_builtin_api_providers()
