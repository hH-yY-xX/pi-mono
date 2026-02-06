# pi-coding-agent Python Package

## Project Structure

```
pi-coding-agent/
├── pi_coding_agent/
│   ├── __init__.py          # Package exports
│   ├── models.py           # Data models and types
│   ├── session_manager.py  # Session management core
│   └── compaction.py       # Context compression logic
├── examples/
│   └── basic_usage.py      # Usage examples
├── tests/
│   └── test_session_manager.py  # Unit tests
├── setup.py                # Setup configuration
├── pyproject.toml          # Project configuration
└── README.md              # Documentation
```

## Key Components

### 1. Data Models (`models.py`)
- Pydantic models for all message types
- Session entry definitions
- Context structures
- Enumerations for roles and levels

### 2. Session Manager (`session_manager.py`)
- Tree-based session management
- JSONL persistence
- Branching and navigation
- Context building for LLM consumption

### 3. Compaction Manager (`compaction.py`)
- Token estimation and monitoring
- Cut point detection algorithms
- File operation tracking
- Preparation for summary generation

## Usage Patterns

### Basic Session Management
```python
from pi_coding_agent import SessionManager

# Create session
session = SessionManager.create("/project/path")

# Add messages
session.append_message({"role": "user", "content": "Hello"})
session.append_message({"role": "assistant", "content": "Hi there!"})

# Get context for LLM
context = session.build_session_context()
```

### Context Compression
```python
from pi_coding_agent import CompactionManager, CompactionSettings

# Check if compaction needed
settings = CompactionSettings()
should_compress = CompactionManager.should_compact(
    context_tokens=50000,
    context_window=128000,
    settings=settings
)

# Prepare for compaction
entries = session.get_entries()
preparation = CompactionManager.prepare_compaction(entries, settings)
```

## Design Principles

1. **Compatibility**: Maintains JSONL format compatibility with original TypeScript version
2. **Extensibility**: Supports custom message types and extension entries
3. **Type Safety**: Uses Pydantic for robust data validation
4. **Performance**: Efficient tree traversal and indexing
5. **Migration**: Handles version upgrades automatically

## Differences from TypeScript Version

- Uses Pydantic instead of TypeScript interfaces
- Pythonic naming conventions (snake_case)
- Simplified file I/O operations
- Compatible JSON serialization
- Same core algorithms and data structures