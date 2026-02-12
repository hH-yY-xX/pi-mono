"""Providers package."""

from pi_ai.providers.simple_options import (
    adjust_max_tokens_for_thinking,
    build_base_options,
    clamp_reasoning,
)
from pi_ai.providers.transform_messages import transform_messages
from pi_ai.providers.anthropic import (
    AnthropicOptions,
    stream_anthropic,
    stream_simple_anthropic,
)
from pi_ai.providers.openai_completions import (
    OpenAICompletionsOptions,
    stream_openai_completions,
    stream_simple_openai_completions,
)
from pi_ai.providers.register_builtins import (
    register_builtin_api_providers,
    reset_api_providers,
)

__all__ = [
    # Simple options
    "adjust_max_tokens_for_thinking",
    "build_base_options",
    "clamp_reasoning",
    # Transform messages
    "transform_messages",
    # Anthropic
    "AnthropicOptions",
    "stream_anthropic",
    "stream_simple_anthropic",
    # OpenAI Completions
    "OpenAICompletionsOptions",
    "stream_openai_completions",
    "stream_simple_openai_completions",
    # Register builtins
    "register_builtin_api_providers",
    "reset_api_providers",
]
