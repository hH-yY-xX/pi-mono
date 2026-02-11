#!/usr/bin/env python3

import json
import os
from pathlib import Path
from typing import Any, Dict, List, TypedDict, Union, Optional
from urllib.parse import urljoin
import httpx

# Type definitions
class Cost(TypedDict):
    input: float
    output: float
    cacheRead: float
    cacheWrite: float

class Model(TypedDict):
    id: str
    name: str
    api: str
    provider: str
    baseUrl: str
    reasoning: bool
    input: List[str]
    cost: Cost
    contextWindow: int
    maxTokens: int
    headers: Optional[Dict[str, str]]
    compat: Optional[Dict[str, Any]]

class ModelsDevModel(TypedDict):
    id: str
    name: str
    tool_call: Optional[bool]
    reasoning: Optional[bool]
    limit: Optional[Dict[str, int]]
    cost: Optional[Dict[str, float]]
    modalities: Optional[Dict[str, List[str]]]
    provider: Optional[Dict[str, str]]
    status: Optional[str]

class AiGatewayModel(TypedDict):
    id: str
    name: Optional[str]
    context_window: Optional[int]
    max_tokens: Optional[int]
    tags: Optional[List[str]]
    pricing: Optional[Dict[str, Union[str, float]]]

# Constants
COPILOT_STATIC_HEADERS = {
    "User-Agent": "GitHubCopilotChat/0.35.0",
    "Editor-Version": "vscode/1.107.0",
    "Editor-Plugin-Version": "copilot-chat/0.35.0",
    "Copilot-Integration-Id": "vscode-chat",
}

AI_GATEWAY_MODELS_URL = "https://ai-gateway.vercel.sh/v1"
AI_GATEWAY_BASE_URL = "https://ai-gateway.vercel.sh"

def to_number(value: Union[str, float, None]) -> float:
    """Convert string or numeric value to number, returning 0 for invalid values."""
    if isinstance(value, (int, float)):
        return float(value) if not (isinstance(value, float) and not value.is_finite()) else 0.0
    try:
        parsed = float(value or "0")
        return parsed if parsed.is_finite() else 0.0
    except (ValueError, TypeError):
        return 0.0

async def fetch_openrouter_models() -> List[Model]:
    """Fetch models from OpenRouter API."""
    try:
        print("Fetching models from OpenRouter API...")
        async with httpx.AsyncClient() as client:
            response = await client.get("https://openrouter.ai/api/v1/models")
            data = response.json()
        
        models: List[Model] = []
        
        for model in data.get("data", []):
            # Only include models that support tools
            if "tools" not in model.get("supported_parameters", []):
                continue
            
            model_key = model["id"]
            
            # Parse input modalities
            input_modalities = ["text"]
            if "image" in model.get("architecture", {}).get("modality", []):
                input_modalities.append("image")
            
            # Convert pricing from $/token to $/million tokens
            pricing = model.get("pricing", {})
            input_cost = to_number(pricing.get("prompt", "0")) * 1_000_000
            output_cost = to_number(pricing.get("completion", "0")) * 1_000_000
            cache_read_cost = to_number(pricing.get("input_cache_read", "0")) * 1_000_000
            cache_write_cost = to_number(pricing.get("input_cache_write", "0")) * 1_000_000
            
            normalized_model: Model = {
                "id": model_key,
                "name": model["name"],
                "api": "openai-completions",
                "baseUrl": "https://openrouter.ai/api/v1",
                "provider": "openrouter",
                "reasoning": "reasoning" in model.get("supported_parameters", []),
                "input": input_modalities,
                "cost": {
                    "input": input_cost,
                    "output": output_cost,
                    "cacheRead": cache_read_cost,
                    "cacheWrite": cache_write_cost,
                },
                "contextWindow": model.get("context_length", 4096),
                "maxTokens": model.get("top_provider", {}).get("max_completion_tokens", 4096),
                "headers": None,
                "compat": None,
            }
            models.append(normalized_model)
        
        print(f"Fetched {len(models)} tool-capable models from OpenRouter")
        return models
    except Exception as error:
        print(f"Failed to fetch OpenRouter models: {error}")
        return []

async def fetch_ai_gateway_models() -> List[Model]:
    """Fetch models from Vercel AI Gateway API."""
    try:
        print("Fetching models from Vercel AI Gateway API...")
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{AI_GATEWAY_MODELS_URL}/models")
            data = response.json()
        
        models: List[Model] = []
        items = data.get("data", []) if isinstance(data.get("data"), list) else []
        
        for model_data in items:
            model: AiGatewayModel = model_data
            tags = model.get("tags", [])
            
            # Only include models that support tools
            if "tool-use" not in tags:
                continue
            
            input_modalities = ["text"]
            if "vision" in tags:
                input_modalities.append("image")
            
            pricing = model.get("pricing", {})
            input_cost = to_number(pricing.get("input", 0)) * 1_000_000
            output_cost = to_number(pricing.get("output", 0)) * 1_000_000
            cache_read_cost = to_number(pricing.get("input_cache_read", 0)) * 1_000_000
            cache_write_cost = to_number(pricing.get("input_cache_write", 0)) * 1_000_000
            
            models.append({
                "id": model["id"],
                "name": model.get("name", model["id"]),
                "api": "anthropic-messages",
                "baseUrl": AI_GATEWAY_BASE_URL,
                "provider": "vercel-ai-gateway",
                "reasoning": "reasoning" in tags,
                "input": input_modalities,
                "cost": {
                    "input": input_cost,
                    "output": output_cost,
                    "cacheRead": cache_read_cost,
                    "cacheWrite": cache_write_cost,
                },
                "contextWindow": model.get("context_window", 4096),
                "maxTokens": model.get("max_tokens", 4096),
                "headers": None,
                "compat": None,
            })
        
        print(f"Fetched {len(models)} tool-capable models from Vercel AI Gateway")
        return models
    except Exception as error:
        print(f"Failed to fetch Vercel AI Gateway models: {error}")
        return []

async def load_models_dev_data() -> List[Model]:
    """Load models from models.dev API."""
    try:
        print("Fetching models from models.dev API...")
        async with httpx.AsyncClient() as client:
            response = await client.get("https://models.dev/api.json")
            data = response.json()
        
        models: List[Model] = []
        
        # Process Amazon Bedrock models
        bedrock_data = data.get("amazon-bedrock", {}).get("models", {})
        for model_id, model_data in bedrock_data.items():
            model: ModelsDevModel = model_data
            if model.get("tool_call") is not True:
                continue
            
            if model_id.startswith("ai21.jamba"):
                # These models don't support tool use in streaming mode
                continue
            
            if model_id.startswith("mistral.mistral-7b-instruct-v0"):
                # These models don't support system messages
                continue
            
            modalities_input = model.get("modalities", {}).get("input", [])
            models.append({
                "id": model_id,
                "name": model.get("name", model_id),
                "api": "bedrock-converse-stream",
                "provider": "amazon-bedrock",
                "baseUrl": "https://bedrock-runtime.us-east-1.amazonaws.com",
                "reasoning": model.get("reasoning") is True,
                "input": ["text", "image"] if "image" in modalities_input else ["text"],
                "cost": {
                    "input": model.get("cost", {}).get("input", 0),
                    "output": model.get("cost", {}).get("output", 0),
                    "cacheRead": model.get("cost", {}).get("cache_read", 0),
                    "cacheWrite": model.get("cost", {}).get("cache_write", 0),
                },
                "contextWindow": model.get("limit", {}).get("context", 4096),
                "maxTokens": model.get("limit", {}).get("output", 4096),
                "headers": None,
                "compat": None,
            })
        
        # Process Anthropic models
        anthropic_data = data.get("anthropic", {}).get("models", {})
        for model_id, model_data in anthropic_data.items():
            model: ModelsDevModel = model_data
            if model.get("tool_call") is not True:
                continue
            
            modalities_input = model.get("modalities", {}).get("input", [])
            models.append({
                "id": model_id,
                "name": model.get("name", model_id),
                "api": "anthropic-messages",
                "provider": "anthropic",
                "baseUrl": "https://api.anthropic.com",
                "reasoning": model.get("reasoning") is True,
                "input": ["text", "image"] if "image" in modalities_input else ["text"],
                "cost": {
                    "input": model.get("cost", {}).get("input", 0),
                    "output": model.get("cost", {}).get("output", 0),
                    "cacheRead": model.get("cost", {}).get("cache_read", 0),
                    "cacheWrite": model.get("cost", {}).get("cache_write", 0),
                },
                "contextWindow": model.get("limit", {}).get("context", 4096),
                "maxTokens": model.get("limit", {}).get("output", 4096),
                "headers": None,
                "compat": None,
            })
        
        # Process Google models
        google_data = data.get("google", {}).get("models", {})
        for model_id, model_data in google_data.items():
            model: ModelsDevModel = model_data
            if model.get("tool_call") is not True:
                continue
            
            modalities_input = model.get("modalities", {}).get("input", [])
            models.append({
                "id": model_id,
                "name": model.get("name", model_id),
                "api": "google-generative-ai",
                "provider": "google",
                "baseUrl": "https://generativelanguage.googleapis.com/v1beta",
                "reasoning": model.get("reasoning") is True,
                "input": ["text", "image"] if "image" in modalities_input else ["text"],
                "cost": {
                    "input": model.get("cost", {}).get("input", 0),
                    "output": model.get("cost", {}).get("output", 0),
                    "cacheRead": model.get("cost", {}).get("cache_read", 0),
                    "cacheWrite": model.get("cost", {}).get("cache_write", 0),
                },
                "contextWindow": model.get("limit", {}).get("context", 4096),
                "maxTokens": model.get("limit", {}).get("output", 4096),
                "headers": None,
                "compat": None,
            })
        
        # Process OpenAI models
        openai_data = data.get("openai", {}).get("models", {})
        for model_id, model_data in openai_data.items():
            model: ModelsDevModel = model_data
            if model.get("tool_call") is not True:
                continue
            
            modalities_input = model.get("modalities", {}).get("input", [])
            models.append({
                "id": model_id,
                "name": model.get("name", model_id),
                "api": "openai-responses",
                "provider": "openai",
                "baseUrl": "https://api.openai.com/v1",
                "reasoning": model.get("reasoning") is True,
                "input": ["text", "image"] if "image" in modalities_input else ["text"],
                "cost": {
                    "input": model.get("cost", {}).get("input", 0),
                    "output": model.get("cost", {}).get("output", 0),
                    "cacheRead": model.get("cost", {}).get("cache_read", 0),
                    "cacheWrite": model.get("cost", {}).get("cache_write", 0),
                },
                "contextWindow": model.get("limit", {}).get("context", 4096),
                "maxTokens": model.get("limit", {}).get("output", 4096),
                "headers": None,
                "compat": None,
            })
        
        # Process Groq models
        groq_data = data.get("groq", {}).get("models", {})
        for model_id, model_data in groq_data.items():
            model: ModelsDevModel = model_data
            if model.get("tool_call") is not True:
                continue
            
            modalities_input = model.get("modalities", {}).get("input", [])
            models.append({
                "id": model_id,
                "name": model.get("name", model_id),
                "api": "openai-completions",
                "provider": "groq",
                "baseUrl": "https://api.groq.com/openai/v1",
                "reasoning": model.get("reasoning") is True,
                "input": ["text", "image"] if "image" in modalities_input else ["text"],
                "cost": {
                    "input": model.get("cost", {}).get("input", 0),
                    "output": model.get("cost", {}).get("output", 0),
                    "cacheRead": model.get("cost", {}).get("cache_read", 0),
                    "cacheWrite": model.get("cost", {}).get("cache_write", 0),
                },
                "contextWindow": model.get("limit", {}).get("context", 4096),
                "maxTokens": model.get("limit", {}).get("output", 4096),
                "headers": None,
                "compat": None,
            })
        
        # Process Cerebras models
        cerebras_data = data.get("cerebras", {}).get("models", {})
        for model_id, model_data in cerebras_data.items():
            model: ModelsDevModel = model_data
            if model.get("tool_call") is not True:
                continue
            
            modalities_input = model.get("modalities", {}).get("input", [])
            models.append({
                "id": model_id,
                "name": model.get("name", model_id),
                "api": "openai-completions",
                "provider": "cerebras",
                "baseUrl": "https://api.cerebras.ai/v1",
                "reasoning": model.get("reasoning") is True,
                "input": ["text", "image"] if "image" in modalities_input else ["text"],
                "cost": {
                    "input": model.get("cost", {}).get("input", 0),
                    "output": model.get("cost", {}).get("output", 0),
                    "cacheRead": model.get("cost", {}).get("cache_read", 0),
                    "cacheWrite": model.get("cost", {}).get("cache_write", 0),
                },
                "contextWindow": model.get("limit", {}).get("context", 4096),
                "maxTokens": model.get("limit", {}).get("output", 4096),
                "headers": None,
                "compat": None,
            })
        
        # Process xAI models
        xai_data = data.get("xai", {}).get("models", {})
        for model_id, model_data in xai_data.items():
            model: ModelsDevModel = model_data
            if model.get("tool_call") is not True:
                continue
            
            modalities_input = model.get("modalities", {}).get("input", [])
            models.append({
                "id": model_id,
                "name": model.get("name", model_id),
                "api": "openai-completions",
                "provider": "xai",
                "baseUrl": "https://api.x.ai/v1",
                "reasoning": model.get("reasoning") is True,
                "input": ["text", "image"] if "image" in modalities_input else ["text"],
                "cost": {
                    "input": model.get("cost", {}).get("input", 0),
                    "output": model.get("cost", {}).get("output", 0),
                    "cacheRead": model.get("cost", {}).get("cache_read", 0),
                    "cacheWrite": model.get("cost", {}).get("cache_write", 0),
                },
                "contextWindow": model.get("limit", {}).get("context", 4096),
                "maxTokens": model.get("limit", {}).get("output", 4096),
                "headers": None,
                "compat": None,
            })
        
        # Process zAi models
        zai_data = data.get("zai", {}).get("models", {})
        for model_id, model_data in zai_data.items():
            model: ModelsDevModel = model_data
            if model.get("tool_call") is not True:
                continue
            
            modalities_input = model.get("modalities", {}).get("input", [])
            supports_image = "image" in modalities_input
            
            models.append({
                "id": model_id,
                "name": model.get("name", model_id),
                "api": "openai-completions",
                "provider": "zai",
                "baseUrl": "https://api.z.ai/api/coding/paas/v4",
                "reasoning": model.get("reasoning") is True,
                "input": ["text", "image"] if supports_image else ["text"],
                "cost": {
                    "input": model.get("cost", {}).get("input", 0),
                    "output": model.get("cost", {}).get("output", 0),
                    "cacheRead": model.get("cost", {}).get("cache_read", 0),
                    "cacheWrite": model.get("cost", {}).get("cache_write", 0),
                },
                "contextWindow": model.get("limit", {}).get("context", 4096),
                "maxTokens": model.get("limit", {}).get("output", 4096),
                "headers": None,
                "compat": {
                    "supportsDeveloperRole": False,
                    "thinkingFormat": "zai",
                },
            })
        
        # Process Mistral models
        mistral_data = data.get("mistral", {}).get("models", {})
        for model_id, model_data in mistral_data.items():
            model: ModelsDevModel = model_data
            if model.get("tool_call") is not True:
                continue
            
            modalities_input = model.get("modalities", {}).get("input", [])
            models.append({
                "id": model_id,
                "name": model.get("name", model_id),
                "api": "openai-completions",
                "provider": "mistral",
                "baseUrl": "https://api.mistral.ai/v1",
                "reasoning": model.get("reasoning") is True,
                "input": ["text", "image"] if "image" in modalities_input else ["text"],
                "cost": {
                    "input": model.get("cost", {}).get("input", 0),
                    "output": model.get("cost", {}).get("output", 0),
                    "cacheRead": model.get("cost", {}).get("cache_read", 0),
                    "cacheWrite": model.get("cost", {}).get("cache_write", 0),
                },
                "contextWindow": model.get("limit", {}).get("context", 4096),
                "maxTokens": model.get("limit", {}).get("output", 4096),
                "headers": None,
                "compat": None,
            })
        
        # Process Hugging Face models
        huggingface_data = data.get("huggingface", {}).get("models", {})
        for model_id, model_data in huggingface_data.items():
            model: ModelsDevModel = model_data
            if model.get("tool_call") is not True:
                continue
            
            modalities_input = model.get("modalities", {}).get("input", [])
            models.append({
                "id": model_id,
                "name": model.get("name", model_id),
                "api": "openai-completions",
                "provider": "huggingface",
                "baseUrl": "https://router.huggingface.co/v1",
                "reasoning": model.get("reasoning") is True,
                "input": ["text", "image"] if "image" in modalities_input else ["text"],
                "cost": {
                    "input": model.get("cost", {}).get("input", 0),
                    "output": model.get("cost", {}).get("output", 0),
                    "cacheRead": model.get("cost", {}).get("cache_read", 0),
                    "cacheWrite": model.get("cost", {}).get("cache_write", 0),
                },
                "contextWindow": model.get("limit", {}).get("context", 4096),
                "maxTokens": model.get("limit", {}).get("output", 4096),
                "headers": None,
                "compat": {
                    "supportsDeveloperRole": False,
                },
            })
        
        # Process OpenCode Zen models
        opencode_data = data.get("opencode", {}).get("models", {})
        for model_id, model_data in opencode_data.items():
            model: ModelsDevModel = model_data
            if model.get("tool_call") is not True:
                continue
            if model.get("status") == "deprecated":
                continue
            
            npm = model.get("provider", {}).get("npm")
            
            if npm == "@ai-sdk/openai":
                api = "openai-responses"
                base_url = "https://opencode.ai/zen/v1"
            elif npm == "@ai-sdk/anthropic":
                api = "anthropic-messages"
                base_url = "https://opencode.ai/zen"  # Anthropic SDK appends /v1/messages
            elif npm == "@ai-sdk/google":
                api = "google-generative-ai"
                base_url = "https://opencode.ai/zen/v1"
            else:
                # null, undefined, or @ai-sdk/openai-compatible
                api = "openai-completions"
                base_url = "https://opencode.ai/zen/v1"
            
            modalities_input = model.get("modalities", {}).get("input", [])
            models.append({
                "id": model_id,
                "name": model.get("name", model_id),
                "api": api,
                "provider": "opencode",
                "baseUrl": base_url,
                "reasoning": model.get("reasoning") is True,
                "input": ["text", "image"] if "image" in modalities_input else ["text"],
                "cost": {
                    "input": model.get("cost", {}).get("input", 0),
                    "output": model.get("cost", {}).get("output", 0),
                    "cacheRead": model.get("cost", {}).get("cache_read", 0),
                    "cacheWrite": model.get("cost", {}).get("cache_write", 0),
                },
                "contextWindow": model.get("limit", {}).get("context", 4096),
                "maxTokens": model.get("limit", {}).get("output", 4096),
                "headers": None,
                "compat": None,
            })
        
        # Process GitHub Copilot models
        copilot_data = data.get("github-copilot", {}).get("models", {})
        for model_id, model_data in copilot_data.items():
            model: ModelsDevModel = model_data
            if model.get("tool_call") is not True:
                continue
            if model.get("status") == "deprecated":
                continue
            
            # gpt-5 models require responses API, others use completions
            needs_responses_api = model_id.startswith("gpt-5") or model_id.startswith("oswe")
            
            copilot_model: Model = {
                "id": model_id,
                "name": model.get("name", model_id),
                "api": "openai-responses" if needs_responses_api else "openai-completions",
                "provider": "github-copilot",
                "baseUrl": "https://api.individual.githubcopilot.com",
                "reasoning": model.get("reasoning") is True,
                "input": ["text", "image"] if "image" in model.get("modalities", {}).get("input", []) else ["text"],
                "cost": {
                    "input": model.get("cost", {}).get("input", 0),
                    "output": model.get("cost", {}).get("output", 0),
                    "cacheRead": model.get("cost", {}).get("cache_read", 0),
                    "cacheWrite": model.get("cost", {}).get("cache_write", 0),
                },
                "contextWindow": model.get("limit", {}).get("context", 128000),
                "maxTokens": model.get("limit", {}).get("output", 8192),
                "headers": dict(COPILOT_STATIC_HEADERS),
                "compat": None if needs_responses_api else {
                    "supportsStore": False,
                    "supportsDeveloperRole": False,
                    "supportsReasoningEffort": False,
                },
            }
            models.append(copilot_model)
        
        # Process MiniMax models
        minimax_variants = [
            {"key": "minimax", "provider": "minimax", "baseUrl": "https://api.minimax.io/anthropic"},
            {"key": "minimax-cn", "provider": "minimax-cn", "baseUrl": "https://api.minimaxi.com/anthropic"},
        ]
        
        for variant in minimax_variants:
            key = variant["key"]
            provider = variant["provider"]
            base_url = variant["baseUrl"]
            
            minimax_data = data.get(key, {}).get("models", {})
            for model_id, model_data in minimax_data.items():
                model: ModelsDevModel = model_data
                if model.get("tool_call") is not True:
                    continue
                
                modalities_input = model.get("modalities", {}).get("input", [])
                models.append({
                    "id": model_id,
                    "name": model.get("name", model_id),
                    "api": "anthropic-messages",
                    "provider": provider,
                    # MiniMax's Anthropic-compatible API - SDK appends /v1/messages
                    "baseUrl": base_url,
                    "reasoning": model.get("reasoning") is True,
                    "input": ["text", "image"] if "image" in modalities_input else ["text"],
                    "cost": {
                        "input": model.get("cost", {}).get("input", 0),
                        "output": model.get("cost", {}).get("output", 0),
                        "cacheRead": model.get("cost", {}).get("cache_read", 0),
                        "cacheWrite": model.get("cost", {}).get("cache_write", 0),
                    },
                    "contextWindow": model.get("limit", {}).get("context", 4096),
                    "maxTokens": model.get("limit", {}).get("output", 4096),
                    "headers": None,
                    "compat": None,
                })
        
        # Process Kimi For Coding models
        kimi_data = data.get("kimi-for-coding", {}).get("models", {})
        for model_id, model_data in kimi_data.items():
            model: ModelsDevModel = model_data
            if model.get("tool_call") is not True:
                continue
            
            modalities_input = model.get("modalities", {}).get("input", [])
            models.append({
                "id": model_id,
                "name": model.get("name", model_id),
                "api": "anthropic-messages",
                "provider": "kimi-coding",
                # Kimi For Coding's Anthropic-compatible API - SDK appends /v1/messages
                "baseUrl": "https://api.kimi.com/coding",
                "reasoning": model.get("reasoning") is True,
                "input": ["text", "image"] if "image" in modalities_input else ["text"],
                "cost": {
                    "input": model.get("cost", {}).get("input", 0),
                    "output": model.get("cost", {}).get("output", 0),
                    "cacheRead": model.get("cost", {}).get("cache_read", 0),
                    "cacheWrite": model.get("cost", {}).get("cache_write", 0),
                },
                "contextWindow": model.get("limit", {}).get("context", 4096),
                "maxTokens": model.get("limit", {}).get("output", 4096),
                "headers": None,
                "compat": None,
            })
        
        print(f"Loaded {len(models)} tool-capable models from models.dev")
        return models
    except Exception as error:
        print(f"Failed to load models.dev data: {error}")
        return []

def add_missing_models(all_models: List[Model]) -> List[Model]:
    """Add missing models that aren't in the API sources."""
    
    # Fix incorrect cache pricing for Claude Opus 4.5 from models.dev
    # models.dev has 3x the correct pricing (1.5/18.75 instead of 0.5/6.25)
    for model in all_models:
        if model["provider"] == "anthropic" and model["id"] == "claude-opus-4-5":
            model["cost"]["cacheRead"] = 0.5
            model["cost"]["cacheWrite"] = 6.25
    
    # Add missing gpt models
    if not any(m["provider"] == "openai" and m["id"] == "gpt-5-chat-latest" for m in all_models):
        all_models.append({
            "id": "gpt-5-chat-latest",
            "name": "GPT-5 Chat Latest",
            "api": "openai-responses",
            "baseUrl": "https://api.openai.com/v1",
            "provider": "openai",
            "reasoning": False,
            "input": ["text", "image"],
            "cost": {
                "input": 1.25,
                "output": 10,
                "cacheRead": 0.125,
                "cacheWrite": 0,
            },
            "contextWindow": 128000,
            "maxTokens": 16384,
            "headers": None,
            "compat": None,
        })
    
    if not any(m["provider"] == "openai" and m["id"] == "gpt-5.1-codex" for m in all_models):
        all_models.append({
            "id": "gpt-5.1-codex",
            "name": "GPT-5.1 Codex",
            "api": "openai-responses",
            "baseUrl": "https://api.openai.com/v1",
            "provider": "openai",
            "reasoning": True,
            "input": ["text", "image"],
            "cost": {
                "input": 1.25,
                "output": 5,
                "cacheRead": 0.125,
                "cacheWrite": 1.25,
            },
            "contextWindow": 400000,
            "maxTokens": 128000,
            "headers": None,
            "compat": None,
        })
    
    if not any(m["provider"] == "openai" and m["id"] == "gpt-5.1-codex-max" for m in all_models):
        all_models.append({
            "id": "gpt-5.1-codex-max",
            "name": "GPT-5.1 Codex Max",
            "api": "openai-responses",
            "baseUrl": "https://api.openai.com/v1",
            "provider": "openai",
            "reasoning": True,
            "input": ["text", "image"],
            "cost": {
                "input": 1.25,
                "output": 10,
                "cacheRead": 0.125,
                "cacheWrite": 0,
            },
            "contextWindow": 400000,
            "maxTokens": 128000,
            "headers": None,
            "compat": None,
        })
    
    # OpenAI Codex (ChatGPT OAuth) models
    CODEX_BASE_URL = "https://chatgpt.com/backend-api"
    CODEX_CONTEXT = 272000
    CODEX_MAX_TOKENS = 128000
    codex_models: List[Model] = [
        {
            "id": "gpt-5.1",
            "name": "GPT-5.1",
            "api": "openai-codex-responses",
            "provider": "openai-codex",
            "baseUrl": CODEX_BASE_URL,
            "reasoning": True,
            "input": ["text", "image"],
            "cost": {"input": 1.25, "output": 10, "cacheRead": 0.125, "cacheWrite": 0},
            "contextWindow": CODEX_CONTEXT,
            "maxTokens": CODEX_MAX_TOKENS,
            "headers": None,
            "compat": None,
        },
        {
            "id": "gpt-5.1-codex-max",
            "name": "GPT-5.1 Codex Max",
            "api": "openai-codex-responses",
            "provider": "openai-codex",
            "baseUrl": CODEX_BASE_URL,
            "reasoning": True,
            "input": ["text", "image"],
            "cost": {"input": 1.25, "output": 10, "cacheRead": 0.125, "cacheWrite": 0},
            "contextWindow": CODEX_CONTEXT,
            "maxTokens": CODEX_MAX_TOKENS,
            "headers": None,
            "compat": None,
        },
        {
            "id": "gpt-5.1-codex-mini",
            "name": "GPT-5.1 Codex Mini",
            "api": "openai-codex-responses",
            "provider": "openai-codex",
            "baseUrl": CODEX_BASE_URL,
            "reasoning": True,
            "input": ["text", "image"],
            "cost": {"input": 0.25, "output": 2, "cacheRead": 0.025, "cacheWrite": 0},
            "contextWindow": CODEX_CONTEXT,
            "maxTokens": CODEX_MAX_TOKENS,
            "headers": None,
            "compat": None,
        },
        {
            "id": "gpt-5.2",
            "name": "GPT-5.2",
            "api": "openai-codex-responses",
            "provider": "openai-codex",
            "baseUrl": CODEX_BASE_URL,
            "reasoning": True,
            "input": ["text", "image"],
            "cost": {"input": 1.75, "output": 14, "cacheRead": 0.175, "cacheWrite": 0},
            "contextWindow": CODEX_CONTEXT,
            "maxTokens": CODEX_MAX_TOKENS,
            "headers": None,
            "compat": None,
        },
        {
            "id": "gpt-5.2-codex",
            "name": "GPT-5.2 Codex",
            "api": "openai-codex-responses",
            "provider": "openai-codex",
            "baseUrl": CODEX_BASE_URL,
            "reasoning": True,
            "input": ["text", "image"],
            "cost": {"input": 1.75, "output": 14, "cacheRead": 0.175, "cacheWrite": 0},
            "contextWindow": CODEX_CONTEXT,
            "maxTokens": CODEX_MAX_TOKENS,
            "headers": None,
            "compat": None,
        },
    ]
    all_models.extend(codex_models)
    
    # Add missing Grok models
    if not any(m["provider"] == "xai" and m["id"] == "grok-code-fast-1" for m in all_models):
        all_models.append({
            "id": "grok-code-fast-1",
            "name": "Grok Code Fast 1",
            "api": "openai-completions",
            "baseUrl": "https://api.x.ai/v1",
            "provider": "xai",
            "reasoning": False,
            "input": ["text"],
            "cost": {
                "input": 0.2,
                "output": 1.5,
                "cacheRead": 0.02,
                "cacheWrite": 0,
            },
            "contextWindow": 32768,
            "maxTokens": 8192,
            "headers": None,
            "compat": None,
        })
    
    # Add missing OpenRouter model
    if not any(m["provider"] == "openrouter" and m["id"] == "openrouter/auto" for m in all_models):
        all_models.append({
            "id": "openrouter/auto",
            "name": "OpenRouter: Auto Router",
            "api": "openai-completions",
            "provider": "openrouter",
            "baseUrl": "https://openrouter.ai/api/v1",
            "reasoning": True,
            "input": ["text", "image"],
            "cost": {
                # we dont know about the costs because OpenRouter auto routes to different models
                # and then charges you for the underlying used model
                "input": 0,
                "output": 0,
                "cacheRead": 0,
                "cacheWrite": 0,
            },
            "contextWindow": 2000000,
            "maxTokens": 30000,
            "headers": None,
            "compat": None,
        })
    
    # Google Cloud Code Assist models (Gemini CLI)
    CLOUD_CODE_ASSIST_ENDPOINT = "https://cloudcode-pa.googleapis.com"
    cloud_code_assist_models: List[Model] = [
        {
            "id": "gemini-2.5-pro",
            "name": "Gemini 2.5 Pro (Cloud Code Assist)",
            "api": "google-gemini-cli",
            "provider": "google-gemini-cli",
            "baseUrl": CLOUD_CODE_ASSIST_ENDPOINT,
            "reasoning": True,
            "input": ["text", "image"],
            "cost": {"input": 0, "output": 0, "cacheRead": 0, "cacheWrite": 0},
            "contextWindow": 1048576,
            "maxTokens": 65535,
            "headers": None,
            "compat": None,
        },
        {
            "id": "gemini-2.5-flash",
            "name": "Gemini 2.5 Flash (Cloud Code Assist)",
            "api": "google-gemini-cli",
            "provider": "google-gemini-cli",
            "baseUrl": CLOUD_CODE_ASSIST_ENDPOINT,
            "reasoning": True,
            "input": ["text", "image"],
            "cost": {"input": 0, "output": 0, "cacheRead": 0, "cacheWrite": 0},
            "contextWindow": 1048576,
            "maxTokens": 65535,
            "headers": None,
            "compat": None,
        },
        {
            "id": "gemini-2.0-flash",
            "name": "Gemini 2.0 Flash (Cloud Code Assist)",
            "api": "google-gemini-cli",
            "provider": "google-gemini-cli",
            "baseUrl": CLOUD_CODE_ASSIST_ENDPOINT,
            "reasoning": False,
            "input": ["text", "image"],
            "cost": {"input": 0, "output": 0, "cacheRead": 0, "cacheWrite": 0},
            "contextWindow": 1048576,
            "maxTokens": 8192,
            "headers": None,
            "compat": None,
        },
        {
            "id": "gemini-3-pro-preview",
            "name": "Gemini 3 Pro Preview (Cloud Code Assist)",
            "api": "google-gemini-cli",
            "provider": "google-gemini-cli",
            "baseUrl": CLOUD_CODE_ASSIST_ENDPOINT,
            "reasoning": True,
            "input": ["text", "image"],
            "cost": {"input": 0, "output": 0, "cacheRead": 0, "cacheWrite": 0},
            "contextWindow": 1048576,
            "maxTokens": 65535,
            "headers": None,
            "compat": None,
        },
        {
            "id": "gemini-3-flash-preview",
            "name": "Gemini 3 Flash Preview (Cloud Code Assist)",
            "api": "google-gemini-cli",
            "provider": "google-gemini-cli",
            "baseUrl": CLOUD_CODE_ASSIST_ENDPOINT,
            "reasoning": True,
            "input": ["text", "image"],
            "cost": {"input": 0, "output": 0, "cacheRead": 0, "cacheWrite": 0},
            "contextWindow": 1048576,
            "maxTokens": 65535,
            "headers": None,
            "compat": None,
        },
    ]
    all_models.extend(cloud_code_assist_models)
    
    # Antigravity models (Gemini 3, Claude, GPT-OSS via Google Cloud)
    ANTIGRAVITY_ENDPOINT = "https://daily-cloudcode-pa.sandbox.googleapis.com"
    antigravity_models: List[Model] = [
        {
            "id": "gemini-3-pro-high",
            "name": "Gemini 3 Pro High (Antigravity)",
            "api": "google-gemini-cli",
            "provider": "google-antigravity",
            "baseUrl": ANTIGRAVITY_ENDPOINT,
            "reasoning": True,
            "input": ["text", "image"],
            # the Model type doesn't seem to support having extended-context costs, so I'm just using the pricing for <200k input
            "cost": {"input": 2, "output": 12, "cacheRead": 0.2, "cacheWrite": 2.375},
            "contextWindow": 1048576,
            "maxTokens": 65535,
            "headers": None,
            "compat": None,
        },
        {
            "id": "gemini-3-pro-low",
            "name": "Gemini 3 Pro Low (Antigravity)",
            "api": "google-gemini-cli",
            "provider": "google-antigravity",
            "baseUrl": ANTIGRAVITY_ENDPOINT,
            "reasoning": True,
            "input": ["text", "image"],
            # the Model type doesn't seem to support having extended-context costs, so I'm just using the pricing for <200k input
            "cost": {"input": 2, "output": 12, "cacheRead": 0.2, "cacheWrite": 2.375},
            "contextWindow": 1048576,
            "maxTokens": 65535,
            "headers": None,
            "compat": None,
        },
        {
            "id": "gemini-3-flash",
            "name": "Gemini 3 Flash (Antigravity)",
            "api": "google-gemini-cli",
            "provider": "google-antigravity",
            "baseUrl": ANTIGRAVITY_ENDPOINT,
            "reasoning": True,
            "input": ["text", "image"],
            "cost": {"input": 0.5, "output": 3, "cacheRead": 0.5, "cacheWrite": 0},
            "contextWindow": 1048576,
            "maxTokens": 65535,
            "headers": None,
            "compat": None,
        },
        {
            "id": "claude-sonnet-4-5",
            "name": "Claude Sonnet 4.5 (Antigravity)",
            "api": "google-gemini-cli",
            "provider": "google-antigravity",
            "baseUrl": ANTIGRAVITY_ENDPOINT,
            "reasoning": False,
            "input": ["text", "image"],
            "cost": {"input": 3, "output": 15, "cacheRead": 0.3, "cacheWrite": 3.75},
            "contextWindow": 200000,
            "maxTokens": 64000,
            "headers": None,
            "compat": None,
        },
        {
            "id": "claude-sonnet-4-5-thinking",
            "name": "Claude Sonnet 4.5 Thinking (Antigravity)",
            "api": "google-gemini-cli",
            "provider": "google-antigravity",
            "baseUrl": ANTIGRAVITY_ENDPOINT,
            "reasoning": True,
            "input": ["text", "image"],
            "cost": {"input": 3, "output": 15, "cacheRead": 0.3, "cacheWrite": 3.75},
            "contextWindow": 200000,
            "maxTokens": 64000,
            "headers": None,
            "compat": None,
        },
        {
            "id": "claude-opus-4-5-thinking",
            "name": "Claude Opus 4.5 Thinking (Antigravity)",
            "api": "google-gemini-cli",
            "provider": "google-antigravity",
            "baseUrl": ANTIGRAVITY_ENDPOINT,
            "reasoning": True,
            "input": ["text", "image"],
            "cost": {"input": 5, "output": 25, "cacheRead": 0.5, "cacheWrite": 6.25},
            "contextWindow": 200000,
            "maxTokens": 64000,
            "headers": None,
            "compat": None,
        },
        {
            "id": "gpt-oss-120b-medium",
            "name": "GPT-OSS 120B Medium (Antigravity)",
            "api": "google-gemini-cli",
            "provider": "google-antigravity",
            "baseUrl": ANTIGRAVITY_ENDPOINT,
            "reasoning": False,
            "input": ["text"],
            "cost": {"input": 0.09, "output": 0.36, "cacheRead": 0, "cacheWrite": 0},
            "contextWindow": 131072,
            "maxTokens": 32768,
            "headers": None,
            "compat": None,
        },
    ]
    all_models.extend(antigravity_models)
    
    # Vertex models
    VERTEX_BASE_URL = "https://{location}-aiplatform.googleapis.com"
    vertex_models: List[Model] = [
        {
            "id": "gemini-3-pro-preview",
            "name": "Gemini 3 Pro Preview (Vertex)",
            "api": "google-vertex",
            "provider": "google-vertex",
            "baseUrl": VERTEX_BASE_URL,
            "reasoning": True,
            "input": ["text", "image"],
            "cost": {"input": 2, "output": 12, "cacheRead": 0.2, "cacheWrite": 0},
            "contextWindow": 1000000,
            "maxTokens": 64000,
            "headers": None,
            "compat": None,
        },
        {
            "id": "gemini-3-flash-preview",
            "name": "Gemini 3 Flash Preview (Vertex)",
            "api": "google-vertex",
            "provider": "google-vertex",
            "baseUrl": VERTEX_BASE_URL,
            "reasoning": True,
            "input": ["text", "image"],
            "cost": {"input": 0.5, "output": 3, "cacheRead": 0.05, "cacheWrite": 0},
            "contextWindow": 1048576,
            "maxTokens": 65536,
            "headers": None,
            "compat": None,
        },
        {
            "id": "gemini-2.0-flash",
            "name": "Gemini 2.0 Flash (Vertex)",
            "api": "google-vertex",
            "provider": "google-vertex",
            "baseUrl": VERTEX_BASE_URL,
            "reasoning": False,
            "input": ["text", "image"],
            "cost": {"input": 0.15, "output": 0.6, "cacheRead": 0.0375, "cacheWrite": 0},
            "contextWindow": 1048576,
            "maxTokens": 8192,
            "headers": None,
            "compat": None,
        },
        {
            "id": "gemini-2.0-flash-lite",
            "name": "Gemini 2.0 Flash Lite (Vertex)",
            "api": "google-vertex",
            "provider": "google-vertex",
            "baseUrl": VERTEX_BASE_URL,
            "reasoning": True,
            "input": ["text", "image"],
            "cost": {"input": 0.075, "output": 0.3, "cacheRead": 0.01875, "cacheWrite": 0},
            "contextWindow": 1048576,
            "maxTokens": 65536,
            "headers": None,
            "compat": None,
        },
        {
            "id": "gemini-2.5-pro",
            "name": "Gemini 2.5 Pro (Vertex)",
            "api": "google-vertex",
            "provider": "google-vertex",
            "baseUrl": VERTEX_BASE_URL,
            "reasoning": True,
            "input": ["text", "image"],
            "cost": {"input": 1.25, "output": 10, "cacheRead": 0.125, "cacheWrite": 0},
            "contextWindow": 1048576,
            "maxTokens": 65536,
            "headers": None,
            "compat": None,
        },
        {
            "id": "gemini-2.5-flash",
            "name": "Gemini 2.5 Flash (Vertex)",
            "api": "google-vertex",
            "provider": "google-vertex",
            "baseUrl": VERTEX_BASE_URL,
            "reasoning": True,
            "input": ["text", "image"],
            "cost": {"input": 0.3, "output": 2.5, "cacheRead": 0.03, "cacheWrite": 0},
            "contextWindow": 1048576,
            "maxTokens": 65536,
            "headers": None,
            "compat": None,
        },
        {
            "id": "gemini-2.5-flash-lite-preview-09-2025",
            "name": "Gemini 2.5 Flash Lite Preview 09-25 (Vertex)",
            "api": "google-vertex",
            "provider": "google-vertex",
            "baseUrl": VERTEX_BASE_URL,
            "reasoning": True,
            "input": ["text", "image"],
            "cost": {"input": 0.1, "output": 0.4, "cacheRead": 0.01, "cacheWrite": 0},
            "contextWindow": 1048576,
            "maxTokens": 65536,
            "headers": None,
            "compat": None,
        },
        {
            "id": "gemini-2.5-flash-lite",
            "name": "Gemini 2.5 Flash Lite (Vertex)",
            "api": "google-vertex",
            "provider": "google-vertex",
            "baseUrl": VERTEX_BASE_URL,
            "reasoning": True,
            "input": ["text", "image"],
            "cost": {"input": 0.1, "output": 0.4, "cacheRead": 0.01, "cacheWrite": 0},
            "contextWindow": 1048576,
            "maxTokens": 65536,
            "headers": None,
            "compat": None,
        },
        {
            "id": "gemini-1.5-pro",
            "name": "Gemini 1.5 Pro (Vertex)",
            "api": "google-vertex",
            "provider": "google-vertex",
            "baseUrl": VERTEX_BASE_URL,
            "reasoning": False,
            "input": ["text", "image"],
            "cost": {"input": 1.25, "output": 5, "cacheRead": 0.3125, "cacheWrite": 0},
            "contextWindow": 1000000,
            "maxTokens": 8192,
            "headers": None,
            "compat": None,
        },
        {
            "id": "gemini-1.5-flash",
            "name": "Gemini 1.5 Flash (Vertex)",
            "api": "google-vertex",
            "provider": "google-vertex",
            "baseUrl": VERTEX_BASE_URL,
            "reasoning": False,
            "input": ["text", "image"],
            "cost": {"input": 0.075, "output": 0.3, "cacheRead": 0.01875, "cacheWrite": 0},
            "contextWindow": 1000000,
            "maxTokens": 8192,
            "headers": None,
            "compat": None,
        },
        {
            "id": "gemini-1.5-flash-8b",
            "name": "Gemini 1.5 Flash-8B (Vertex)",
            "api": "google-vertex",
            "provider": "google-vertex",
            "baseUrl": VERTEX_BASE_URL,
            "reasoning": False,
            "input": ["text", "image"],
            "cost": {"input": 0.0375, "output": 0.15, "cacheRead": 0.01, "cacheWrite": 0},
            "contextWindow": 1000000,
            "maxTokens": 8192,
            "headers": None,
            "compat": None,
        },
    ]
    all_models.extend(vertex_models)
    
    # Kimi For Coding models (Moonshot AI's Anthropic-compatible coding API)
    # Static fallback in case models.dev doesn't have them yet
    KIMI_CODING_BASE_URL = "https://api.kimi.com/coding"
    kimi_coding_models: List[Model] = [
        {
            "id": "kimi-k2-thinking",
            "name": "Kimi K2 Thinking",
            "api": "anthropic-messages",
            "provider": "kimi-coding",
            "baseUrl": KIMI_CODING_BASE_URL,
            "reasoning": True,
            "input": ["text"],
            "cost": {"input": 0, "output": 0, "cacheRead": 0, "cacheWrite": 0},
            "contextWindow": 262144,
            "maxTokens": 32768,
            "headers": None,
            "compat": None,
        },
        {
            "id": "k2p5",
            "name": "Kimi K2.5",
            "api": "anthropic-messages",
            "provider": "kimi-coding",
            "baseUrl": KIMI_CODING_BASE_URL,
            "reasoning": True,
            "input": ["text"],
            "cost": {"input": 0, "output": 0, "cacheRead": 0, "cacheWrite": 0},
            "contextWindow": 262144,
            "maxTokens": 32768,
            "headers": None,
            "compat": None,
        },
    ]
    # Only add if not already present from models.dev
    for model in kimi_coding_models:
        if not any(m["provider"] == "kimi-coding" and m["id"] == model["id"] for m in all_models):
            all_models.append(model)
    
    # Azure OpenAI models
    azure_openai_models = [
        {
            **model,
            "api": "azure-openai-responses",
            "provider": "azure-openai-responses",
            "baseUrl": "",
        }
        for model in all_models
        if model["provider"] == "openai" and model["api"] == "openai-responses"
    ]
    all_models.extend(azure_openai_models)
    
    return all_models

def generate_models_file(all_models: List[Model], output_path: Path) -> None:
    """Generate the Python models file."""
    # Group by provider and deduplicate by model ID
    providers: Dict[str, Dict[str, Model]] = {}
    for model in all_models:
        provider = model["provider"]
        if provider not in providers:
            providers[provider] = {}
        # Use model ID as key to automatically deduplicate
        # Only add if not already present (models.dev takes priority over OpenRouter)
        if model["id"] not in providers[provider]:
            providers[provider][model["id"]] = model
    
    # Generate Python file
    output = '''# This file is auto-generated by scripts/generate_models.py
# Do not edit manually - run 'python scripts/generate_models.py' to update

from typing import Dict, List, TypedDict, Literal

# Type definitions for model structure
class Cost(TypedDict):
    input: float
    output: float
    cacheRead: float
    cacheWrite: float

class Model(TypedDict):
    id: str
    name: str
    api: str
    provider: str
    baseUrl: str
    reasoning: bool
    input: List[str]
    cost: Cost
    contextWindow: int
    maxTokens: int

MODELS: Dict[str, Dict[str, Model]] = {
'''
    
    # Generate provider sections (sorted for deterministic output)
    sorted_provider_ids = sorted(providers.keys())
    for provider_id in sorted_provider_ids:
        models = providers[provider_id]
        output += f'    "{provider_id}": {{\n'
        
        sorted_model_ids = sorted(models.keys())
        for model_id in sorted_model_ids:
            model = models[model_id]
            output += f'        "{model["id"]}": {{\n'
            output += f'            "id": "{model["id"]}",\n'
            output += f'            "name": "{model["name"]}",\n'
            output += f'            "api": "{model["api"]}",\n'
            output += f'            "provider": "{model["provider"]}",\n'
            output += f'            "baseUrl": "{model["baseUrl"]}",\n'
            output += f'            "reasoning": {str(model["reasoning"]).lower()},\n'
            input_str = ", ".join([f'"{inp}"' for inp in model["input"]])
            output += f'            "input": [{input_str}],\n'
            output += '            "cost": {\n'
            output += f'                "input": {model["cost"]["input"]},\n'
            output += f'                "output": {model["cost"]["output"]},\n'
            output += f'                "cacheRead": {model["cost"]["cacheRead"]},\n'
            output += f'                "cacheWrite": {model["cost"]["cacheWrite"]},\n'
            output += '            },\n'
            output += f'            "contextWindow": {model["contextWindow"]},\n'
            output += f'            "maxTokens": {model["maxTokens"]},\n'
            output += '        },\n'
        
        output += '    },\n'
    
    output += '}\n'
    
    # Write file
    output_path.write_text(output, encoding='utf-8')
    print(f"Generated {output_path}")

def print_statistics(all_models: List[Model], providers: Dict[str, Dict[str, Model]]) -> None:
    """Print model statistics."""
    total_models = len(all_models)
    reasoning_models = len([m for m in all_models if m["reasoning"]])
    
    print("\nModel Statistics:")
    print(f"  Total tool-capable models: {total_models}")
    print(f"  Reasoning-capable models: {reasoning_models}")
    
    for provider, models in providers.items():
        print(f"  {provider}: {len(models)} models")

async def generate_models() -> None:
    """Main function to generate models."""
    # Fetch models from both sources
    # models.dev: Anthropic, Google, OpenAI, Groq, Cerebras
    # OpenRouter: xAI and other providers (excluding Anthropic, Google, OpenAI)
    # AI Gateway: OpenAI-compatible catalog with tool-capable models
    models_dev_models = await load_models_dev_data()
    open_router_models = await fetch_openrouter_models()
    ai_gateway_models = await fetch_ai_gateway_models()
    
    # Combine models (models.dev has priority)
    all_models = models_dev_models + open_router_models + ai_gateway_models
    
    # Add missing models
    all_models = add_missing_models(all_models)
    
    # Get package root and output path
    script_dir = Path(__file__).parent
    package_root = script_dir.parent
    output_path = package_root / "src" / "models_generated.py"
    
    # Generate the models file
    generate_models_file(all_models, output_path)
    
    # Group by provider for statistics
    providers: Dict[str, Dict[str, Model]] = {}
    for model in all_models:
        provider = model["provider"]
        if provider not in providers:
            providers[provider] = {}
        if model["id"] not in providers[provider]:
            providers[provider][model["id"]] = model
    
    # Print statistics
    print_statistics(all_models, providers)

if __name__ == "__main__":
    import asyncio
    asyncio.run(generate_models())