"""
Core streaming interface for AI providers.
"""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .types import (
        Api,
        AssistantMessage,
        AssistantMessageEventStream,
        Context,
        Model,
        ProviderStreamOptions,
        SimpleStreamOptions,
        StreamOptions,
    )

from .api_registry import get_api_provider
from .env_api_keys import get_env_api_key

def stream(
    model: 'Model',
    context: 'Context',
    options: 'ProviderStreamOptions' = None,
) -> 'AssistantMessageEventStream':
    """
    Stream completion using the specified model and provider.
    
    Args:
        model: The model to use
        context: The conversation context
        options: Streaming options
        
    Returns:
        An event stream for the completion
        
    Raises:
        ValueError: If no provider is registered for the model's API
    """
    provider = _resolve_api_provider(model.api)
    return provider.stream(model, context, options or {})

async def complete(
    model: 'Model',
    context: 'Context',
    options: 'ProviderStreamOptions' = None,
) -> 'AssistantMessage':
    """
    Complete a conversation and return the final message.
    
    Args:
        model: The model to use
        context: The conversation context
        options: Streaming options
        
    Returns:
        The completed assistant message
    """
    s = stream(model, context, options)
    return await s.result()

def stream_simple(
    model: 'Model',
    context: 'Context',
    options: 'SimpleStreamOptions' = None,
) -> 'AssistantMessageEventStream':
    """
    Stream completion with simplified options.
    
    Args:
        model: The model to use
        context: The conversation context
        options: Simplified streaming options
        
    Returns:
        An event stream for the completion
        
    Raises:
        ValueError: If no provider is registered for the model's API
    """
    provider = _resolve_api_provider(model.api)
    return provider.stream_simple(model, context, options or {})

async def complete_simple(
    model: 'Model',
    context: 'Context',
    options: 'SimpleStreamOptions' = None,
) -> 'AssistantMessage':
    """
    Complete a conversation with simplified options and return the final message.
    
    Args:
        model: The model to use
        context: The conversation context
        options: Simplified streaming options
        
    Returns:
        The completed assistant message
    """
    s = stream_simple(model, context, options)
    return await s.result()

def _resolve_api_provider(api: 'Api'):
    """
    Resolve API provider for the given API type.
    
    Args:
        api: The API type
        
    Returns:
        The API provider
        
    Raises:
        ValueError: If no provider is registered for the API
    """
    provider = get_api_provider(api)
    if not provider:
        raise ValueError(f"No API provider registered for api: {api}")
    return provider