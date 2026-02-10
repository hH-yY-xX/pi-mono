"""
Register built-in API providers.
"""

from .api_registry import register_api_provider, clear_api_providers
from .providers.anthropic import AnthropicProvider
from .providers.openai import OpenAIProvider
from .providers.google import GoogleProvider

def register_built_in_api_providers() -> None:
    """Register all built-in API providers."""
    
    # Register Anthropic provider
    register_api_provider(AnthropicProvider())
    
    # Register OpenAI provider  
    register_api_provider(OpenAIProvider())
    
    # Register Google provider
    register_api_provider(GoogleProvider())

def reset_api_providers() -> None:
    """Reset API providers to built-in defaults."""
    clear_api_providers()
    register_built_in_api_providers()

# Register providers on import
register_built_in_api_providers()