"""
Environment variable API key resolution.
"""

from __future__ import annotations

import os
from pathlib import Path

from pi_ai.types import KnownProvider

_cached_vertex_adc_credentials_exists: bool | None = None


def _has_vertex_adc_credentials() -> bool:
    """Check if Vertex AI ADC credentials exist."""
    global _cached_vertex_adc_credentials_exists
    
    if _cached_vertex_adc_credentials_exists is None:
        # Check GOOGLE_APPLICATION_CREDENTIALS env var first
        gac_path = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
        if gac_path:
            _cached_vertex_adc_credentials_exists = Path(gac_path).exists()
        else:
            # Fall back to default ADC path
            default_path = Path.home() / ".config" / "gcloud" / "application_default_credentials.json"
            _cached_vertex_adc_credentials_exists = default_path.exists()
    
    return _cached_vertex_adc_credentials_exists


def get_env_api_key(provider: KnownProvider | str) -> str | None:
    """
    Get API key for provider from known environment variables.
    
    Will not return API keys for providers that require OAuth tokens.
    
    Args:
        provider: The provider name (e.g., "openai", "anthropic")
    
    Returns:
        The API key, or None if not found.
    """
    # GitHub Copilot
    if provider == "github-copilot":
        return (
            os.environ.get("COPILOT_GITHUB_TOKEN")
            or os.environ.get("GH_TOKEN")
            or os.environ.get("GITHUB_TOKEN")
        )

    # Anthropic - OAuth token takes precedence
    if provider == "anthropic":
        return os.environ.get("ANTHROPIC_OAUTH_TOKEN") or os.environ.get("ANTHROPIC_API_KEY")

    # Google Vertex AI - uses Application Default Credentials
    if provider == "google-vertex":
        has_credentials = _has_vertex_adc_credentials()
        has_project = bool(
            os.environ.get("GOOGLE_CLOUD_PROJECT") or os.environ.get("GCLOUD_PROJECT")
        )
        has_location = bool(os.environ.get("GOOGLE_CLOUD_LOCATION"))

        if has_credentials and has_project and has_location:
            return "<authenticated>"
        return None

    # Amazon Bedrock - supports multiple credential sources
    if provider == "amazon-bedrock":
        if (
            os.environ.get("AWS_PROFILE")
            or (os.environ.get("AWS_ACCESS_KEY_ID") and os.environ.get("AWS_SECRET_ACCESS_KEY"))
            or os.environ.get("AWS_BEARER_TOKEN_BEDROCK")
            or os.environ.get("AWS_CONTAINER_CREDENTIALS_RELATIVE_URI")
            or os.environ.get("AWS_CONTAINER_CREDENTIALS_FULL_URI")
            or os.environ.get("AWS_WEB_IDENTITY_TOKEN_FILE")
        ):
            return "<authenticated>"
        return None

    # Standard environment variable mappings
    env_map: dict[str, str] = {
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
