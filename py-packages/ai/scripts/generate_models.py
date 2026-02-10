#!/usr/bin/env python3
"""
Generate model definitions for the AI package.
This script fetches model information from various LLM providers
and generates the models.py file with all available models.
"""

import json
import httpx
import asyncio
from pathlib import Path
from typing import List, Dict, Any
from dataclasses import asdict

# Import our types
from src.types import Model, UsageCost, KnownProvider, Api

MODELS_FILE = Path(__file__).parent / "src" / "models_generated.py"
PACKAGE_ROOT = Path(__file__).parent

COPILOT_STATIC_HEADERS = {
    "User-Agent": "GitHubCopilotChat/0.35.0",
    "Editor-Version": "vscode/1.107.0",
    "Editor-Plugin-Version": "copilot-chat/0.35.0",
    "Copilot-Integration-Id": "vscode-chat",
}

AI_GATEWAY_MODELS_URL = "https://ai-gateway.vercel.sh/v1"
AI_GATEWAY_BASE_URL = "https://ai-gateway.vercel.sh"


async def fetch_openrouter_models() -> List[Model]:
    """Fetch models from OpenRouter API."""
    print("Fetching models from OpenRouter API...")
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get("https://openrouter.ai/api/v1/models")
            response.raise_for_status()
            data = response.json()
            
            models = []
            for model_data in data.get("data", []):
                # Only include models that support tools
                if "tools" not in model_data.get("supported_parameters", []):
                    continue
                
                # Parse provider from model ID
                provider: KnownProvider = "openrouter"
                model_key = model_data["id"]
                
                # Parse input modalities
                input_modalities = ["text"]
                if "image" in model_data.get("architecture", {}).get("modality", []):
                    input_modalities.append("image")
                
                # Convert pricing from $/token to $/million tokens
                pricing = model_data.get("pricing", {})
                input_cost = float(pricing.get("prompt", "0")) * 1_000_000
                output_cost = float(pricing.get("completion", "0")) * 1_000_000
                cache_read_cost = float(pricing.get("input_cache_read", "0")) * 1_000_000
                cache_write_cost = float(pricing.get("input_cache_write", "0")) * 1_000_000
                
                model = Model(
                    id=model_key,
                    name=model_data["name"],
                    api="openai-completions",
                    provider=provider,
                    base_url="https://openrouter.ai/api/v1",
                    reasoning="reasoning" in model_data.get("supported_parameters", []),
                    input=input_modalities,
                    cost=UsageCost(
                        input=input_cost,
                        output=output_cost,
                        cache_read=cache_read_cost,
                        cache_write=cache_write_cost,
                        total=input_cost + output_cost
                    ),
                    context_window=model_data.get("context_length", 4096),
                    max_tokens=model_data.get("top_provider", {}).get("max_completion_tokens", 4096)
                )
                models.append(model)
            
            print(f"Fetched {len(models)} models from OpenRouter")
            return models
            
        except Exception as e:
            print(f"Failed to fetch OpenRouter models: {e}")
            return []


async def fetch_anthropic_models() -> List[Model]:
    """Define Anthropic models statically."""
    print("Defining Anthropic models...")
    models = [
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
        )
    ]
    print(f"Defined {len(models)} Anthropic models")
    return models


async def fetch_openai_models() -> List[Model]:
    """Define OpenAI models statically."""
    print("Defining OpenAI models...")
    models = [
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
        )
    ]
    print(f"Defined {len(models)} OpenAI models")
    return models


async def fetch_google_models() -> List[Model]:
    """Define Google models statically."""
    print("Defining Google models...")
    models = [
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
        )
    ]
    print(f"Defined {len(models)} Google models")
    return models


def generate_models_file(models: List[Model]) -> str:
    """Generate the models.py file content."""
    header = '''"""
Auto-generated model definitions.
Do not edit manually - run generate_models.py instead.
"""

from typing import List
from .types import Model

# Auto-generated model list
MODELS: List[Model] = [
'''
    
    model_entries = []
    for model in models:
        model_dict = asdict(model)
        # Convert cost to dict for serialization
        cost_dict = asdict(model_dict.pop('cost'))
        
        entry = f'''    Model(
        id="{model_dict['id']}",
        name="{model_dict['name']}",
        api="{model_dict['api']}",
        provider="{model_dict['provider']}",
        base_url="{model_dict['base_url']}",
        reasoning={model_dict['reasoning']},
        input={model_dict['input']},
        cost=UsageCost(**{cost_dict}),
        context_window={model_dict['context_window']},
        max_tokens={model_dict['max_tokens']}'''
        
        if model_dict['headers']:
            entry += f''',
        headers={model_dict['headers']}'''
        
        entry += '''
    ),'''
        model_entries.append(entry)
    
    footer = '''
]

# Model lookup by ID
MODEL_BY_ID = {model.id: model for model in MODELS}

def get_model(model_id: str) -> Model:
    """Get a model by its ID."""
    return MODEL_BY_ID.get(model_id)

def list_models() -> List[Model]:
    """List all available models."""
    return MODELS.copy()
'''
    
    return header + '\n'.join(model_entries) + '\n]' + footer


async def main():
    """Main entry point."""
    print("Generating model definitions...")
    
    # Fetch models from all providers
    tasks = [
        fetch_openrouter_models(),
        fetch_anthropic_models(),
        fetch_openai_models(),
        fetch_google_models()
    ]
    
    results = await asyncio.gather(*tasks)
    all_models = []
    for models in results:
        all_models.extend(models)
    
    # Sort models by provider and name
    all_models.sort(key=lambda m: (m.provider, m.name))
    
    # Generate the file content
    content = generate_models_file(all_models)
    
    # Write to file
    with open(MODELS_FILE, 'w') as f:
        f.write(content)
    
    print(f"Generated {len(all_models)} models in {MODELS_FILE}")


if __name__ == "__main__":
    asyncio.run(main())