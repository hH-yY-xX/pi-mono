"""
API provider registry system.
"""

"""
API provider registry system.
"""

from typing import Dict, List, Optional, Callable, Any, TYPE_CHECKING
from dataclasses import dataclass

if TYPE_CHECKING:
    from .types import (
        Api,
        AssistantMessageEventStream,
        Context,
        Model,
        SimpleStreamOptions,
        StreamOptions
    )

@dataclass
class ApiProvider:
    """API provider interface."""
    api: 'Api'
    # Using Callable instead of StreamFunction for better type checking
    stream: Callable[['Model', 'Context', Optional[StreamOptions]], 'AssistantMessageEventStream']
    stream_simple: Callable[['Model', 'Context', Optional[SimpleStreamOptions]], 'AssistantMessageEventStream']

# Global registry
_api_provider_registry: Dict[str, ApiProvider] = {}

# Global registry
_api_provider_registry: Dict[str, ApiProvider] = {}

def register_api_provider(provider: ApiProvider) -> None:
    """
    Register an API provider.
    
    Args:
        provider: The API provider to register
    """
    _api_provider_registry[provider.api] = provider

def get_api_provider(api: 'Api') -> Optional[ApiProvider]:
    """
    Get an API provider by API type.
    
    Args:
        api: The API type
        
    Returns:
        The API provider or None if not found
    """
    return _api_provider_registry.get(api)

def get_api_providers() -> List[ApiProvider]:
    """
    Get all registered API providers.
    
    Returns:
        List of all registered API providers
    """
    return list(_api_provider_registry.values())

def unregister_api_provider(api: 'Api') -> bool:
    """
    Unregister an API provider.
    
    Args:
        api: The API type to unregister
        
    Returns:
        True if provider was unregistered, False if not found
    """
    if api in _api_provider_registry:
        del _api_provider_registry[api]
        return True
    return False

def clear_api_providers() -> None:
    """Clear all registered API providers."""
    _api_provider_registry.clear()