"""
pi-ai: Python AI library for streaming LLM interactions.

This package provides a unified interface for interacting with various
LLM providers including OpenAI, Anthropic, Google, and others.
"""

from .src import *

__version__ = "0.51.6"
__author__ = "Mario Zechner"

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