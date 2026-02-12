"""
Model registry and utilities.
"""

from __future__ import annotations

from pi_ai.types import Api, KnownProvider, Model, Usage

# Import generated models
from pi_ai.models_generated import MODELS

_model_registry: dict[str, dict[str, Model]] = {}

# Initialize registry from MODELS on module load
for provider, models in MODELS.items():
    provider_models: dict[str, Model] = {}
    for model_id, model_data in models.items():
        provider_models[model_id] = Model.model_validate(model_data)
    _model_registry[provider] = provider_models


def get_model(provider: KnownProvider, model_id: str) -> Model | None:
    """
    Get a model by provider and model ID.
    
    Args:
        provider: The provider name (e.g., "anthropic", "openai")
        model_id: The model ID (e.g., "claude-3-5-sonnet-20241022")
    
    Returns:
        The model definition, or None if not found.
    """
    provider_models = _model_registry.get(provider)
    if provider_models:
        return provider_models.get(model_id)
    return None


def get_providers() -> list[KnownProvider]:
    """Get all registered provider names."""
    return list(_model_registry.keys())  # type: ignore


def get_models(provider: KnownProvider) -> list[Model]:
    """Get all models for a provider."""
    models = _model_registry.get(provider)
    return list(models.values()) if models else []


def calculate_cost(model: Model, usage: Usage) -> Usage:
    """
    Calculate cost based on model pricing and usage.
    
    Updates the usage.cost fields in place and returns the usage.
    """
    usage.cost.input = (model.cost.input / 1_000_000) * usage.input
    usage.cost.output = (model.cost.output / 1_000_000) * usage.output
    usage.cost.cache_read = (model.cost.cache_read / 1_000_000) * usage.cache_read
    usage.cost.cache_write = (model.cost.cache_write / 1_000_000) * usage.cache_write
    usage.cost.total = (
        usage.cost.input + usage.cost.output + usage.cost.cache_read + usage.cost.cache_write
    )
    return usage


def supports_xhigh(model: Model) -> bool:
    """
    Check if a model supports xhigh thinking level.
    
    Currently only certain OpenAI Codex models support this.
    """
    return "gpt-5.2" in model.id


def models_are_equal(a: Model | None, b: Model | None) -> bool:
    """
    Check if two models are equal by comparing both their id and provider.
    
    Returns False if either model is None.
    """
    if not a or not b:
        return False
    return a.id == b.id and a.provider == b.provider
