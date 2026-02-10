"""
Auto-generated model definitions.
Do not edit manually - run generate_models.py instead.
"""

from typing import List
from .types import Model, UsageCost

# Auto-generated model list
MODELS: List[Model] = [
    Model(
        id="claude-3-5-sonnet-20241022",
        name="Claude 3.5 Sonnet",
        api="anthropic-messages",
        provider="anthropic",
        base_url="https://api.anthropic.com",
        reasoning=True,
        input=["text", "image"],
        cost=UsageCost(
            input=3.00,
            output=15.00,
            cache_read=0.30,
            cache_write=3.75,
            total=18.00
        ),
        context_window=200000,
        max_tokens=8192
    ),
    Model(
        id="claude-3-5-haiku-20241022",
        name="Claude 3.5 Haiku",
        api="anthropic-messages",
        provider="anthropic",
        base_url="https://api.anthropic.com",
        reasoning=True,
        input=["text", "image"],
        cost=UsageCost(
            input=1.00,
            output=5.00,
            cache_read=0.03,
            cache_write=0.30,
            total=6.00
        ),
        context_window=200000,
        max_tokens=8192
    ),
    Model(
        id="gpt-4o",
        name="GPT-4o",
        api="openai-completions",
        provider="openai",
        base_url="https://api.openai.com/v1",
        reasoning=True,
        input=["text", "image"],
        cost=UsageCost(
            input=2.50,
            output=10.00,
            cache_read=0.0,
            cache_write=0.0,
            total=12.50
        ),
        context_window=128000,
        max_tokens=16384
    ),
    Model(
        id="gpt-4o-mini",
        name="GPT-4o Mini",
        api="openai-completions",
        provider="openai",
        base_url="https://api.openai.com/v1",
        reasoning=True,
        input=["text", "image"],
        cost=UsageCost(
            input=0.15,
            output=0.60,
            cache_read=0.0,
            cache_write=0.0,
            total=0.75
        ),
        context_window=128000,
        max_tokens=16384
    ),
    Model(
        id="gemini-2.0-flash-exp",
        name="Gemini 2.0 Flash Experimental",
        api="google-generative-ai",
        provider="google",
        base_url="https://generativelanguage.googleapis.com",
        reasoning=True,
        input=["text", "image"],
        cost=UsageCost(
            input=0.0,
            output=0.0,
            cache_read=0.0,
            cache_write=0.0,
            total=0.0
        ),
        context_window=1048576,
        max_tokens=8192
    ),
    Model(
        id="gemini-1.5-pro",
        name="Gemini 1.5 Pro",
        api="google-generative-ai",
        provider="google",
        base_url="https://generativelanguage.googleapis.com",
        reasoning=True,
        input=["text", "image"],
        cost=UsageCost(
            input=1.25,
            output=5.00,
            cache_read=0.0,
            cache_write=0.0,
            total=6.25
        ),
        context_window=2097152,
        max_tokens=8192
    ),
]

# Model lookup by ID
MODEL_BY_ID = {model.id: model for model in MODELS}

def get_model(model_id: str) -> Model:
    """Get a model by its ID."""
    return MODEL_BY_ID.get(model_id)

def list_models() -> List[Model]:
    """List all available models."""
    return MODELS.copy()