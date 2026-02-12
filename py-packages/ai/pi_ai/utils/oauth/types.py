"""
OAuth types for authentication flows.
"""

from __future__ import annotations

from typing import Any, Protocol

from pydantic import BaseModel, ConfigDict


class OAuthToken(BaseModel):
    """OAuth token."""

    model_config = ConfigDict(extra="forbid")

    access_token: str
    refresh_token: str | None = None
    expires_at: int | None = None
    token_type: str = "Bearer"
    scope: str | None = None


class OAuthConfig(BaseModel):
    """OAuth configuration."""

    model_config = ConfigDict(extra="forbid")

    client_id: str
    authorization_url: str
    token_url: str
    redirect_uri: str = "http://localhost:8080/callback"
    scope: str | None = None


class OAuthTokenStore(Protocol):
    """Protocol for OAuth token storage."""

    def get_token(self, provider: str) -> OAuthToken | None:
        """Get a stored token for a provider."""
        ...

    def set_token(self, provider: str, token: OAuthToken) -> None:
        """Store a token for a provider."""
        ...

    def delete_token(self, provider: str) -> None:
        """Delete a stored token for a provider."""
        ...
