"""
API provider registry system.
"""

from typing import Dict, Optional, TYPE_CHECKING
from .types import Api, StreamFunction, StreamOptions, SimpleStreamOptions

if TYPE_CHECKING:
    from .types import Model, Context, AssistantMessageEventStream

class ApiProvider:
    """Base class for API providers."""
    
    def stream(
        self,
        model: 'Model',
        context: 'Context',
        options: Optional[StreamOptions] = None
    ) -> 'AssistantMessageEventStream':
        """Stream completion using provider-specific API."""
        raise NotImplementedError()
        
    def stream_simple(
        self,
        model: 'Model',
        context: 'Context',
        options: Optional[SimpleStreamOptions] = None
    ) -> 'AssistantMessageEventStream':
        """Stream completion with simplified options."""
        raise NotImplementedError()

# Global provider registry
_provider_registry: Dict[Api, ApiProvider] = {}

def register_api_provider(api: Api, provider: ApiProvider) -> None:
    """Register an API provider."""
    _provider_registry[api] = provider

def get_api_provider(api: Api) -> Optional[ApiProvider]:
    """Get a registered API provider."""
    return _provider_registry.get(api)

def get_registered_apis() -> list[Api]:
    """Get all registered APIs."""
    return list(_provider_registry.keys())