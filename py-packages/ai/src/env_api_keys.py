"""
Environment variable API key handling.
"""

import os
from typing import Optional
from .types import KnownProvider

def get_env_api_key(provider: KnownProvider) -> Optional[str]:
    """
    Get API key for provider from known environment variables.
    
    Args:
        provider: The provider name
        
    Returns:
        API key or None if not found
    """
    # GitHub Copilot tokens
    if provider == "github-copilot":
        return (
            os.environ.get("COPILOT_GITHUB_TOKEN") or
            os.environ.get("GH_TOKEN") or
            os.environ.get("GITHUB_TOKEN")
        )
    
    # Anthropic prioritizes OAuth token over API key
    if provider == "anthropic":
        return (
            os.environ.get("ANTHROPIC_OAUTH_TOKEN") or
            os.environ.get("ANTHROPIC_API_KEY")
        )
    
    # Google Vertex AI uses Application Default Credentials
    if provider == "google-vertex":
        has_credentials = _has_vertex_adc_credentials()
        has_project = bool(
            os.environ.get("GOOGLE_CLOUD_PROJECT") or
            os.environ.get("GCLOUD_PROJECT")
        )
        has_location = bool(os.environ.get("GOOGLE_CLOUD_LOCATION"))
        
        if has_credentials and has_project and has_location:
            return "<authenticated>"
    
    # Amazon Bedrock supports multiple credential sources
    if provider == "amazon-bedrock":
        if (
            os.environ.get("AWS_PROFILE") or
            (os.environ.get("AWS_ACCESS_KEY_ID") and os.environ.get("AWS_SECRET_ACCESS_KEY")) or
            os.environ.get("AWS_BEARER_TOKEN_BEDROCK") or
            os.environ.get("AWS_CONTAINER_CREDENTIALS_RELATIVE_URI") or
            os.environ.get("AWS_CONTAINER_CREDENTIALS_FULL_URI") or
            os.environ.get("AWS_WEB_IDENTITY_TOKEN_FILE")
        ):
            return "<authenticated>"
    
    # Standard API key mapping
    env_map = {
        "openai": "OPENAI_API_KEY",
        "azure-openai-responses": "AZURE_OPENAI_API_KEY",
        "google": "GEMINI_API_KEY",
        "groq": "GROQ_API_KEY",
        "cerebras": "CEREBRAS_API_KEY",
        "xai": "XAI_API_KEY",
        "openrouter": "OPENROUTER_API_KEY",
        "vercel-ai-gateway": "AI_GATEWAY_API_KEY",
        "zai": "ZAI_API_KEY",
        "mistral": "MISTRAL_API_KEY",
        "minimax": "MINIMAX_API_KEY",
        "minimax-cn": "MINIMAX_CN_API_KEY",
        "huggingface": "HF_TOKEN",
        "opencode": "OPENCODE_API_KEY",
        "kimi-coding": "KIMI_API_KEY",
    }
    
    env_var = env_map.get(provider)
    return os.environ.get(env_var) if env_var else None

def _has_vertex_adc_credentials() -> bool:
    """
    Check if Google Application Default Credentials exist.
    
    Returns:
        True if ADC credentials are available
    """
    # Check GOOGLE_APPLICATION_CREDENTIALS env var first
    gac_path = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
    if gac_path:
        return os.path.exists(gac_path)
    
    # Fall back to default ADC path
    home_dir = os.path.expanduser("~")
    adc_path = os.path.join(home_dir, ".config", "gcloud", "application_default_credentials.json")
    return os.path.exists(adc_path)