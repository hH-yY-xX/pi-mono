"""
pi-coding-agent Python Package

A Python port of session management and context compression features
from the pi-coding-agent project.
"""

from .session_manager import SessionManager, SessionContext
from .compaction import CompactionManager, CompactionSettings

__version__ = "0.1.0"
__all__ = ["SessionManager", "SessionContext", "CompactionManager", "CompactionSettings"]