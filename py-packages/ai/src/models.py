"""
Model registry and management system.
"""

from typing import Dict, List, Optional, TypeVar, cast
from .types import (
    Api,
    KnownProvider,
    Model,
    Usage,
    UsageCost
)
from .models_generated import MODELS as GENERATED_MODELS, get_model as get_generated_model

# Initialize registry from generated models
_model_registry: Dict[str, Dict[str, Model]] = {}

# Group models by provider
for model in GENERATED_MODELS:
    if model.provider not in _model_registry:
        _model_registry[model.provider] = {}
    _model_registry[model.provider][model.id] = model

T = TypeVar('T', bound=Api)

def get_model(provider: KnownProvider, model_id: str) -> Model:
    """
    Get a model by provider and model ID.
    
    Args:
        provider: The provider name
        model_id: The model ID
        
    Returns:
        The model object
        
    Raises:
        KeyError: If the model is not found
    """
    provider_models = _model_registry.get(provider)
    if not provider_models:
        raise KeyError(f"No models found for provider: {provider}")
    
    model = provider_models.get(model_id)
    if not model:
        raise KeyError(f"Model {model_id} not found for provider {provider}")
    
    return model

def get_providers() -> List[KnownProvider]:
    """Get all available providers."""
    return list(_model_registry.keys())  # type: ignore

def get_models(provider: KnownProvider) -> List[Model]:
    """Get all models for a provider."""
    provider_models = _model_registry.get(provider, {})
    return list(provider_models.values())

def calculate_cost(model: Model, usage: Usage) -> UsageCost:
    """
    Calculate cost based on model pricing and usage.
    
    Args:
        model: The model used
        usage: The usage statistics
        
    Returns:
        Updated cost information
    """
    usage.cost.input = (model.cost.input / 1_000_000) * usage.input
    usage.cost.output = (model.cost.output / 1_000_000) * usage.output
    usage.cost.cache_read = (model.cost.cache_read / 1_000_000) * usage.cache_read
    usage.cost.cache_write = (model.cost.cache_write / 1_000_000) * usage.cache_write
    usage.cost.total = (
        usage.cost.input + 
        usage.cost.output + 
        usage.cost.cache_read + 
        usage.cost.cache_write
    )
    return usage.cost

def supports_xhigh(model: Model) -> bool:
    """
    Check if a model supports xhigh thinking level.
    
    Args:
        model: The model to check
        
    Returns:
        True if the model supports xhigh thinking
    """
    return "gpt-5.2" in model.id

def models_are_equal(a: Optional[Model], b: Optional[Model]) -> bool:
    """
    Check if two models are equal by comparing their ID and provider.
    
    Args:
        a: First model
        b: Second model
        
    Returns:
        True if models are equal, False otherwise
    """
    if not a or not b:
        return False
    return a.id == b.id and a.provider == b.provider