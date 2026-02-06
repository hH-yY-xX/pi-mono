# pi-ai

Python library for streaming LLM interactions with unified interface across multiple providers.

## Features

- **Unified API**: Single interface for OpenAI, Anthropic, Google, and other providers
- **Streaming Support**: Real-time streaming of responses with granular events
- **Multi-modal**: Text and image input/output support
- **Tool Calling**: Native support for function/tool calling
- **Thinking/Reasoning**: Support for model reasoning capabilities
- **Async/Await**: Fully asynchronous design
- **Type Safety**: Comprehensive type hints

## Installation

```bash
pip install pi-ai
```

## Quick Start

```python
import asyncio
from pi_ai import get_model, stream_simple, TextContent

async def main():
    # Get a model
    model = get_model("openai", "gpt-4o")
    
    # Create context
    context = {
        "messages": [{
            "role": "user",
            "content": "Hello, world!",
            "timestamp": int(asyncio.get_event_loop().time() * 1000)
        }]
    }
    
    # Stream the response
    stream = stream_simple(model, context)
    
    async for event in stream:
        if event["type"] == "text_delta":
            print(event["delta"], end="", flush=True)
    
    # Get final message
    message = await stream.result()
    print(f"\n\nFinal message: {message}")

asyncio.run(main())
```

## Core Concepts

### Models

Models represent specific LLM configurations:

```python
from pi_ai import get_model

# Get specific models
gpt4 = get_model("openai", "gpt-4o")
claude = get_model("anthropic", "claude-3-5-sonnet-20241022")
gemini = get_model("google", "gemini-1.5-pro")
```

### Messages

Three message types are supported:

```python
from pi_ai import UserMessage, AssistantMessage, ToolResultMessage

# User message (text or multimodal)
user_msg = UserMessage(
    role="user",
    content="What's in this image?",
    timestamp=1234567890
)

# Assistant message (with streaming content)
assistant_msg = AssistantMessage(
    role="assistant",
    content=[TextContent(text="The image shows...")],
    api="openai-completions",
    provider="openai",
    model="gpt-4o"
)

# Tool result message
tool_result = ToolResultMessage(
    role="toolResult",
    tool_call_id="call_123",
    tool_name="read_file",
    content=[TextContent(text="File contents...")]
)
```

### Streaming

Two streaming approaches are available:

#### Direct Streaming
```python
from pi_ai import stream

stream_obj = stream(model, context, options)
async for event in stream_obj:
    # Handle events: start, text_delta, toolcall_delta, etc.
    pass
```

#### Simplified Streaming
```python
from pi_ai import stream_simple

stream_obj = stream_simple(model, context, simple_options)
async for event in stream_obj:
    # Same event handling but with simpler options
    pass
```

### Event Types

Streaming emits various event types:

- `start`: Stream initialization
- `text_start`/`text_delta`/`text_end`: Text content streaming
- `thinking_start`/`thinking_delta`/`thinking_end`: Reasoning content (Google-specific)
- `toolcall_start`/`toolcall_delta`/`toolcall_end`: Tool calling
- `done`: Successful completion
- `error`: Error occurred

## Advanced Usage

### Tool Calling

```python
from pi_ai import Tool, Context

class FileReader(Tool):
    name = "read_file"
    description = "Read a file from the filesystem"
    parameters = {
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "File path"}
        }
    }

context = Context(
    system_prompt="You can read files using the read_file tool",
    messages=[user_message],
    tools=[FileReader()]
)

stream = stream_simple(model, context)
```

### Thinking/Reasoning

```python
from pi_ai import SimpleStreamOptions, ThinkingLevel

options = SimpleStreamOptions(
    reasoning=ThinkingLevel.HIGH,  # Enable reasoning
    thinking_budgets={
        "minimal": 128,
        "low": 512,
        "medium": 1024,
        "high": 2048
    }
)

stream = stream_simple(model, context, options)
```

### Multi-modal Input

```python
from pi_ai import ImageContent

# Image content (base64 encoded)
image_content = ImageContent(
    data="base64_encoded_image_data",
    mime_type="image/jpeg"
)

user_message = UserMessage(
    role="user",
    content=[
        TextContent(text="Describe this image:"),
        image_content
    ]
)
```

## Supported Providers

| Provider | API Types | Features |
|----------|-----------|----------|
| OpenAI | `openai-completions`, `openai-responses` | Text, Images, Tools, Reasoning |
| Anthropic | `anthropic-messages` | Text, Images, Tools, Caching |
| Google | `google-generative-ai`, `google-gemini-cli` | Text, Images, Tools, Thinking |
| Amazon Bedrock | `bedrock-converse-stream` | Text, Images, Tools |

## Environment Variables

API keys are loaded from environment variables:

```bash
# Provider-specific
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-...
GOOGLE_API_KEY=...
GOOGLE_GEMINI_CLI_API_KEY=...

# Generic fallback
PI_API_KEY=...
```

## Error Handling

```python
try:
    stream = stream_simple(model, context)
    async for event in stream:
        # Process events
        pass
    message = await stream.result()
except Exception as e:
    print(f"Error: {e}")
```

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for development guidelines.

## License

MIT License - see [LICENSE](LICENSE) file.