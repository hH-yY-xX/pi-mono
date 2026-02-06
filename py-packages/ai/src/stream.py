"""
Core streaming functions.
"""

from typing import Optional, TYPE_CHECKING
from .api_registry import get_api_provider
from .env_api_keys import get_env_api_key

if TYPE_CHECKING:
    from .types import (
        Api,
        Model,
        Context,
        StreamOptions,
        SimpleStreamOptions,
        AssistantMessageEventStream,
        AssistantMessage
    )

def resolve_api_provider(api: Api):
    """Resolve API provider or raise error."""
    provider = get_api_provider(api)
    if not provider:
        raise ValueError(f"No API provider registered for api: {api}")
    return provider

def stream(
    model: 'Model',
    context: 'Context',
    options: Optional['StreamOptions'] = None,
) -> 'AssistantMessageEventStream':
    """
    Stream completion using provider-specific API.
    
    Args:
        model: The model to use
        context: The conversation context
        options: Streaming options
        
    Returns:
        Event stream for the completion
    """
    provider = resolve_api_provider(model.api)
    return provider.stream(model, context, options)

async def complete(
    model: 'Model',
    context: 'Context',
    options: Optional['StreamOptions'] = None,
) -> 'AssistantMessage':
    """
    Complete a conversation and return the final message.
    
    Args:
        model: The model to use
        context: The conversation context
        options: Streaming options
        
    Returns:
        Final assistant message
    """
    s = stream(model, context, options)
    return await s.result()

def stream_simple(
    model: 'Model',
    context: 'Context',
    options: Optional['SimpleStreamOptions'] = None,
) -> 'AssistantMessageEventStream':
    """
    Stream completion with simplified options.
    
    Args:
        model: The model to use
        context: The conversation context
        options: Simplified streaming options
        
    Returns:
        Event stream for the completion
    """
    provider = resolve_api_provider(model.api)
    return provider.stream_simple(model, context, options)

async def complete_simple(
    model: 'Model',
    context: 'Context',
    options: Optional['SimpleStreamOptions'] = None,
) -> 'AssistantMessage':
    """
    Complete a conversation with simplified options and return the final message.
    
    Args:
        model: The model to use
        context: The conversation context
        options: Simplified streaming options
        
    Returns:
        Final assistant message
    """
    s = stream_simple(model, context, options)
    return await s.result()