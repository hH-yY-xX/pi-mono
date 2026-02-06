"""
Register built-in API providers.
"""

# Import providers to trigger registration
from . import anthropic
from . import openai
from . import google

# This module's import triggers registration of all built-in providers
__all__ = ['anthropic', 'openai', 'google']