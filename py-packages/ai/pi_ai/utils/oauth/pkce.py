"""
PKCE (Proof Key for Code Exchange) utilities for OAuth 2.0.
"""

from __future__ import annotations

import base64
import hashlib
import secrets


def generate_pkce_pair() -> tuple[str, str]:
    """
    Generate a PKCE code verifier and challenge pair.
    
    Returns:
        Tuple of (code_verifier, code_challenge)
    """
    # Generate a random code verifier (43-128 characters)
    code_verifier = secrets.token_urlsafe(32)

    # Create the code challenge using SHA256
    digest = hashlib.sha256(code_verifier.encode()).digest()
    code_challenge = base64.urlsafe_b64encode(digest).decode().rstrip("=")

    return code_verifier, code_challenge
