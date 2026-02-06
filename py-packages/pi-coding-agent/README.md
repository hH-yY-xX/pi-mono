# pi-coding-agent Python Package

A Python port of the session management and context compression features from the pi-coding-agent project.

## Features

- **Session Management**: Tree-based conversation sessions with branching support
- **Context Compression**: Automatic context management for long conversations
- **Persistence**: JSONL-based storage with automatic version migration
- **Extensible**: Support for custom message types and extension entries

## Installation

```bash
pip install -e .
```

## Quick Start

```python
from pi_coding_agent import SessionManager, CompactionManager

# Create a new session
session = SessionManager.create("/path/to/project")

# Add messages
session.append_message({
    "role": "user",
    "content": "Hello, I need help with my project"
})

# Check if compaction is needed
settings = CompactionManager.DEFAULT_SETTINGS
entries = session.get_entries()
preparation = CompactionManager.prepare_compaction(entries, settings)

# Get context for LLM
context = session.build_session_context()
```

## Core Components

### SessionManager
Manages conversation trees with support for:
- Branching and navigation
- Persistent storage in JSONL format
- Automatic version migration
- Custom entry types for extensions

### CompactionManager
Handles context compression for long sessions:
- Token estimation and monitoring
- Automatic cut point detection
- File operation tracking
- Summary generation preparation

## Data Models

The package includes comprehensive Pydantic models for:
- Message types (User, Assistant, ToolResult, etc.)
- Session entries (Message, Compaction, BranchSummary, etc.)
- Configuration settings
- Context structures

## Example Usage

See `examples/basic_usage.py` for a complete example demonstrating:
- Session creation and message management
- Context building
- Compaction preparation
- Branching operations

## Architecture Notes

This Python implementation mirrors the TypeScript original while adapting to Python idioms:
- Uses Pydantic for data validation and serialization
- Maintains the same JSONL storage format for compatibility
- Preserves the tree-based session structure
- Supports the same extension mechanisms

## Development

```bash
# Install development dependencies
pip install pytest black mypy

# Run tests
pytest

# Format code
black .

# Type checking
mypy pi_coding_agent/
```