"""
Environment variable API key handling.
"""

import os
from typing import Optional
from .types import Api, Provider

def get_env_api_key(provider: Provider) -> Optional[str]:
    """
    Get API key from environment variables.
    
    Args:
        provider: The provider name
        
    Returns:
        API key if found, None otherwise
    """
    # Provider-specific environment variable mappings
    env_vars = {
        "openai": ["OPENAI_API_KEY", "OPENAI_KEY"],
        "anthropic": ["ANTHROPIC_API_KEY", "ANTHROPIC_KEY"],
        "google": ["GOOGLE_API_KEY", "GEMINI_API_KEY"],
        "google-gemini-cli": ["GOOGLE_GEMINI_CLI_API_KEY"],
        "google-vertex": ["GOOGLE_VERTEX_API_KEY"],
        "azure-openai-responses": ["AZURE_OPENAI_API_KEY"],
        "openai-codex": ["OPENAI_CODEX_API_KEY"],
        "github-copilot": ["GITHUB_COPILOT_API_KEY"],
        "amazon-bedrock": ["AWS_ACCESS_KEY_ID", "BEDROCK_API_KEY"],
        "xai": ["XAI_API_KEY"],
        "groq": ["GROQ_API_KEY"],
        "cerebras": ["CEREBRAS_API_KEY"],
        "openrouter": ["OPENROUTER_API_KEY"],
        "vercel-ai-gateway": ["VERCEL_AI_GATEWAY_API_KEY"],
        "zai": ["ZAI_API_KEY"],
        "mistral": ["MISTRAL_API_KEY"],
        "minimax": ["MINIMAX_API_KEY"],
        "minimax-cn": ["MINIMAX_CN_API_KEY"],
        "huggingface": ["HUGGINGFACE_API_KEY"],
        "opencode": ["OPENCODE_API_KEY"],
        "kimi-coding": ["KIMI_CODING_API_KEY"],
    }
    
    # Check provider-specific variables
    provider_vars = env_vars.get(provider, [])
    for var in provider_vars:
        key = os.environ.get(var)
        if key:
            return key
    
    # Fallback to generic PI_API_KEY
    return os.environ.get("PI_API_KEY")