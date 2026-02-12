"""
Streaming functions for LLM calls.
"""

from __future__ import annotations

from pi_ai.api_registry import get_api_provider
from pi_ai.event_stream import AssistantMessageEventStream
from pi_ai.types import (
    Api,
    AssistantMessage,
    Context,
    Model,
    SimpleStreamOptions,
    StreamOptions,
)


def _resolve_api_provider(api: Api):
    """Resolve an API provider by API type."""
    provider = get_api_provider(api)
    if not provider:
        raise ValueError(f"No API provider registered for api: {api}")
    return provider


def stream(
    model: Model,
    context: Context,
    options: StreamOptions | None = None,
) -> AssistantMessageEventStream:
    """
    Stream an assistant message from the LLM.
    
    Uses the provider-specific stream function based on the model's API.
    """
    provider = _resolve_api_provider(model.api)
    return provider.stream(model, context, options)


async def complete(
    model: Model,
    context: Context,
    options: StreamOptions | None = None,
) -> AssistantMessage:
    """
    Complete a single assistant message from the LLM.
    
    Streams the response and returns the final message.
    """
    s = stream(model, context, options)
    return await s.result()


def stream_simple(
    model: Model,
    context: Context,
    options: SimpleStreamOptions | None = None,
) -> AssistantMessageEventStream:
    """
    Stream an assistant message using simplified options.
    
    Handles reasoning/thinking levels automatically.
    """
    provider = _resolve_api_provider(model.api)
    return provider.stream_simple(model, context, options)


async def complete_simple(
    model: Model,
    context: Context,
    options: SimpleStreamOptions | None = None,
) -> AssistantMessage:
    """
    Complete a single assistant message using simplified options.
    
    Streams the response and returns the final message.
    """
    s = stream_simple(model, context, options)
    return await s.result()
