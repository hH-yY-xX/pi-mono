"""
AI package main module.
"""

# Import and register built-in providers
from . import providers
from .providers import register_builtins

# Import core functionality
from .api_registry import get_api_provider, register_api_provider
from .env_api_keys import get_env_api_key
from .models import get_model, get_models, get_providers, calculate_cost, supports_xhigh, models_are_equal
from .stream import stream, complete, stream_simple, complete_simple
from .types import *
from .utils.event_stream import AssistantMessageEventStream, create_assistant_message_event_stream
from .utils.json_parse import parse_streaming_json, validate_json_structure
from .utils.sanitize_unicode import sanitize_surrogates, is_valid_unicode, normalize_unicode

# Version info
__version__ = "0.1.0"

# Export main API
__all__ = [
    # Core functions
    "stream",
    "complete", 
    "stream_simple",
    "complete_simple",
    
    # Model management
    "get_model",
    "get_models",
    "get_providers",
    "calculate_cost",
    "supports_xhigh",
    "models_are_equal",
    
    # API management
    "get_api_provider",
    "register_api_provider",
    "get_env_api_key",
    
    # Types
    "Api",
    "Provider",
    "KnownApi",
    "KnownProvider",
    "ThinkingLevel",
    "CacheRetention",
    "TextContent",
    "ThinkingContent", 
    "ImageContent",
    "ToolCall",
    "Usage",
    "UserMessage",
    "AssistantMessage",
    "ToolResultMessage",
    "Message",
    "Tool",
    "Context",
    "StreamOptions",
    "SimpleStreamOptions",
    "Model",
    
    # Events
    "AssistantMessageEvent",
    "AssistantMessageEventStream",
    "create_assistant_message_event_stream",
    
    # Utilities
    "parse_streaming_json",
    "validate_json_structure",
    "sanitize_surrogates",
    "is_valid_unicode",
    "normalize_unicode",
]