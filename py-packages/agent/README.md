# pi-agent-core

Stateful agent with tool execution and event streaming for Python. Built on pi-ai.

## Installation

```bash
pip install pi-agent-core
```

## Quick Start

```python
from pi_agent_core import Agent
# Assuming pi_ai provides getModel function
# from pi_ai import get_model

agent = Agent(AgentOptions(
    initial_state={
        "system_prompt": "You are a helpful assistant.",
        # "model": get_model("anthropic", "claude-sonnet-4-20250514"),
    }
))

def on_event(event):
    if hasattr(event, 'type') and event.type == "message_update":
        if hasattr(event.assistant_message_event, 'type') and event.assistant_message_event.type == "text_delta":
            # Stream just the new text chunk
            print(event.assistant_message_event.delta, end="", flush=True)

agent.subscribe(on_event)

# await agent.prompt("Hello!")  # In async context
```

## Core Concepts

### AgentMessage vs LLM Message

The agent works with `AgentMessage`, a flexible type that can include:
- Standard LLM messages (`user`, `assistant`, `toolResult`)
- Custom app-specific message types

LLMs only understand `user`, `assistant`, and `toolResult`. The `convert_to_llm` function bridges this gap by filtering and transforming messages before each LLM call.

### Message Flow

```
AgentMessage[] → transform_context() → AgentMessage[] → convert_to_llm() → Message[] → LLM
                    (optional)                           (required)
```

1. **transform_context**: Prune old messages, inject external context
2. **convert_to_llm**: Filter out UI-only messages, convert custom types to LLM format

## Event Flow

The agent emits events for UI updates. Understanding the event sequence helps build responsive interfaces.

### prompt() Event Sequence

When you call `prompt("Hello")`:

```
prompt("Hello")
├─ agent_start
├─ turn_start
├─ message_start   { message: userMessage }      # Your prompt
├─ message_end     { message: userMessage }
├─ message_start   { message: assistantMessage } # LLM starts responding
├─ message_update  { message: partial... }       # Streaming chunks
├─ message_update  { message: partial... }
├─ message_end     { message: assistantMessage } # Complete response
├─ turn_end        { message, toolResults: [] }
└─ agent_end       { messages: [...] }
```

### With Tool Calls

If the assistant calls tools, the loop continues:

```
prompt("Read config.json")
├─ agent_start
├─ turn_start
├─ message_start/end  { userMessage }
├─ message_start      { assistantMessage with toolCall }
├─ message_update...
├─ message_end        { assistantMessage }
├─ tool_execution_start  { toolCallId, toolName, args }
├─ tool_execution_update { partialResult }           # If tool streams
├─ tool_execution_end    { toolCallId, result }
├─ message_start/end  { toolResultMessage }
├─ turn_end           { message, toolResults: [toolResult] }
│
├─ turn_start                                        # Next turn
├─ message_start      { assistantMessage }           # LLM responds to tool result
├─ message_update...
├─ message_end
├─ turn_end
└─ agent_end
```

### continue() Event Sequence

`continue_()` resumes from existing context without adding a new message. Use it for retries after errors.

```python
# After an error, retry from current state
# await agent.continue_()
```

The last message in context must be `user` or `toolResult` (not `assistant`).

## Agent Options

```python
agent = Agent(AgentOptions(
    # Initial state
    initial_state={
        "system_prompt": str,
        "model": Model,  # From pi-ai
        "thinking_level": "off" | "minimal" | "low" | "medium" | "high" | "xhigh",
        "tools": [AgentTool],
        "messages": [AgentMessage],
    },

    # Convert AgentMessage[] to LLM Message[] (required for custom message types)
    convert_to_llm=lambda messages: [m for m in messages if m.role in ('user', 'assistant', 'toolResult')],

    # Transform context before convert_to_llm (for pruning, compaction)
    transform_context=async_lambda(messages, signal): prune_old_messages(messages),

    # Steering mode: "one-at-a-time" (default) or "all"
    steering_mode="one-at-a-time",

    # Follow-up mode: "one-at-a-time" (default) or "all"  
    follow_up_mode="one-at-a-time",

    # Custom stream function (for proxy backends)
    stream_fn=stream_proxy,

    # Session ID for provider caching
    session_id="session-123",

    # Dynamic API key resolution (for expiring OAuth tokens)
    get_api_key=async_lambda(provider): refresh_token(),

    # Custom thinking budgets for token-based providers
    thinking_budgets={
        "minimal": 128,
        "low": 512,
        "medium": 1024,
        "high": 2048,
    },
))
```

## Agent State

```python
class AgentState:
    system_prompt: str
    model: Model  # From pi-ai
    thinking_level: ThinkingLevel
    tools: List[AgentTool]
    messages: List[AgentMessage]
    is_streaming: bool
    stream_message: Optional[AgentMessage]  # Current partial during streaming
    pending_tool_calls: Set[str]
    error: Optional[str]
```

Access via `agent.state`. During streaming, `stream_message` contains the partial assistant message.

## Methods

### Prompting

```python
# Text prompt
# await agent.prompt("Hello")

# With images
# await agent.prompt("What's in this image?", [
#     ImageContent(data=base64_data, mime_type="image/jpeg")
# ])

# AgentMessage directly
# await agent.prompt(UserMessage(role="user", content="Hello", timestamp=int(time.time()*1000)))

# Continue from current context (last message must be user or toolResult)
# await agent.continue_()
```

### State Management

```python
agent.set_system_prompt("New prompt")
# agent.set_model(get_model("openai", "gpt-4o"))
agent.set_thinking_level("medium")
agent.set_tools([my_tool])
agent.replace_messages(new_messages)
agent.append_message(message)
agent.clear_messages()
agent.reset()  # Clear everything
```

### Session and Thinking Budgets

```python
agent.session_id = "session-123"

agent.thinking_budgets = {
    "minimal": 128,
    "low": 512,
    "medium": 1024,
    "high": 2048,
}
```

### Control

```python
agent.abort()           # Cancel current operation
# await agent.wait_for_idle()  # Wait for completion
```

### Events

```python
def on_event(event):
    print(event.type)

unsubscribe = agent.subscribe(on_event)
# unsubscribe()  # To unsubscribe
```

## Steering and Follow-up

Steering messages let you interrupt the agent while tools are running. Follow-up messages let you queue work after the agent would otherwise stop.

```python
agent.set_steering_mode("one-at-a-time")
agent.set_follow_up_mode("one-at-a-time")

# While agent is running tools
agent.steer(UserMessage(
    role="user",
    content="Stop! Do this instead.",
    timestamp=int(time.time()*1000)
))

# After the agent finishes its current work
agent.follow_up(UserMessage(
    role="user", 
    content="Also summarize the result.",
    timestamp=int(time.time()*1000)
))

steering_mode = agent.get_steering_mode()
follow_up_mode = agent.get_follow_up_mode()

agent.clear_steering_queue()
agent.clear_follow_up_queue()
agent.clear_all_queues()
```

Use clear_steering_queue, clear_follow_up_queue, or clear_all_queues to drop queued messages.

When steering messages are detected after a tool completes:
1. Remaining tools are skipped with error results
2. Steering messages are injected
3. LLM responds to the interruption

Follow-up messages are checked only when there are no more tool calls and no steering messages. If any are queued, they are injected and another turn runs.

## Tools

Define tools using `AgentTool`:

```python
# Example tool definition (would need actual implementation)
class ReadFileTool:
    def __init__(self):
        self.name = "read_file"
        self.label = "Read File"
        self.description = "Read a file's contents"
        self.parameters = {"path": str}
    
    async def execute(self, tool_call_id, params, signal, on_update):
        # Implementation would go here
        content = "file content"
        
        # Optional: stream progress
        if on_update:
            on_update(AgentToolResult(
                content=[TextContent(text="Reading...")],
                details={}
            ))
            
        return AgentToolResult(
            content=[TextContent(text=content)],
            details={"path": params["path"], "size": len(content)}
        )

# agent.set_tools([ReadFileTool()])
```

### Error Handling

**Raise an exception** when a tool fails. Do not return error messages as content.

```python
async def execute(self, tool_call_id, params, signal, on_update):
    if not os.path.exists(params["path"]):
        raise FileNotFoundError(f"File not found: {params['path']}")
    # Return content only on success
    return AgentToolResult(content=[TextContent(text="...")], details={})
```

Raised exceptions are caught by the agent and reported to the LLM as tool errors with `is_error: True`.

## License

MIT