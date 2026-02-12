"""
Core types for pi-agent.
"""

from __future__ import annotations

from typing import Any, Callable, Literal, Protocol, TypeAlias, TypeVar

from pydantic import BaseModel, ConfigDict, Field

from pi_ai import (
    AssistantMessage,
    AssistantMessageEvent,
    AssistantMessageEventStream,
    Context,
    ImageContent,
    Message,
    Model,
    SimpleStreamOptions,
    TextContent,
    ThinkingBudgets,
    Tool,
    ToolResultMessage,
)

# Thinking level with "off" option
ThinkingLevel: TypeAlias = Literal["off", "minimal", "low", "medium", "high", "xhigh"]


class StreamFn(Protocol):
    """Stream function protocol - can return sync or async."""

    def __call__(
        self,
        model: Model,
        context: Context,
        options: SimpleStreamOptions | None = None,
    ) -> AssistantMessageEventStream:
        ...


class AgentLoopConfig(SimpleStreamOptions):
    """Configuration for the agent loop."""

    model: Model

    convert_to_llm: Callable[["list[AgentMessage]"], list[Message] | "Awaitable[list[Message]]"]
    """
    Converts AgentMessage[] to LLM-compatible Message[] before each LLM call.
    """

    transform_context: Callable[
        ["list[AgentMessage]", "Any | None"], "Awaitable[list[AgentMessage]]"
    ] | None = None
    """
    Optional transform applied to the context before convert_to_llm.
    """

    get_api_key: Callable[[str], "str | None | Awaitable[str | None]"] | None = None
    """
    Resolves an API key dynamically for each LLM call.
    """

    get_steering_messages: Callable[[], "Awaitable[list[AgentMessage]]"] | None = None
    """
    Returns steering messages to inject into the conversation mid-run.
    """

    get_follow_up_messages: Callable[[], "Awaitable[list[AgentMessage]]"] | None = None
    """
    Returns follow-up messages to process after the agent would otherwise stop.
    """


# Type alias for Awaitable
from typing import Awaitable


class CustomAgentMessages:
    """
    Extensible interface for custom app messages.
    
    Apps can extend via subclassing or adding to this dict.
    """

    pass


# AgentMessage: Union of LLM messages + custom messages
AgentMessage: TypeAlias = Message


class AgentState(BaseModel):
    """Agent state containing all configuration and conversation data."""

    model_config = ConfigDict(extra="forbid", arbitrary_types_allowed=True)

    system_prompt: str = ""
    model: Model
    thinking_level: ThinkingLevel = "off"
    tools: list["AgentTool"] = Field(default_factory=list)
    messages: list[AgentMessage] = Field(default_factory=list)
    is_streaming: bool = False
    stream_message: AgentMessage | None = None
    pending_tool_calls: set[str] = Field(default_factory=set)
    error: str | None = None


class AgentToolResult(BaseModel):
    """Result from a tool execution."""

    model_config = ConfigDict(extra="forbid")

    content: list[TextContent | ImageContent]
    details: Any = None


# Callback for streaming tool execution updates
AgentToolUpdateCallback: TypeAlias = Callable[["AgentToolResult"], None]


class AgentTool(Tool):
    """Agent tool with execution function."""

    model_config = ConfigDict(extra="forbid", arbitrary_types_allowed=True)

    label: str
    """Human-readable label for the tool."""

    execute: Callable[
        [str, dict[str, Any], Any | None, AgentToolUpdateCallback | None],
        "Awaitable[AgentToolResult]",
    ]
    """
    Execute the tool.
    
    Args:
        tool_call_id: The tool call ID
        params: The validated parameters
        signal: Optional cancellation signal
        on_update: Optional callback for partial results
    
    Returns:
        The tool result
    """


class AgentContext(BaseModel):
    """Agent context - like Context but uses AgentTool."""

    model_config = ConfigDict(extra="forbid", arbitrary_types_allowed=True)

    system_prompt: str = ""
    messages: list[AgentMessage] = Field(default_factory=list)
    tools: list[AgentTool] | None = None


# Agent Events
class AgentStartEvent(BaseModel):
    """Agent start event."""

    model_config = ConfigDict(extra="forbid")
    type: Literal["agent_start"] = "agent_start"


class AgentEndEvent(BaseModel):
    """Agent end event."""

    model_config = ConfigDict(extra="forbid")
    type: Literal["agent_end"] = "agent_end"
    messages: list[AgentMessage]


class TurnStartEvent(BaseModel):
    """Turn start event."""

    model_config = ConfigDict(extra="forbid")
    type: Literal["turn_start"] = "turn_start"


class TurnEndEvent(BaseModel):
    """Turn end event."""

    model_config = ConfigDict(extra="forbid")
    type: Literal["turn_end"] = "turn_end"
    message: AgentMessage
    tool_results: list[ToolResultMessage]


class MessageStartEvent(BaseModel):
    """Message start event."""

    model_config = ConfigDict(extra="forbid")
    type: Literal["message_start"] = "message_start"
    message: AgentMessage


class MessageUpdateEvent(BaseModel):
    """Message update event (only for assistant messages during streaming)."""

    model_config = ConfigDict(extra="forbid", arbitrary_types_allowed=True)
    type: Literal["message_update"] = "message_update"
    message: AgentMessage
    assistant_message_event: AssistantMessageEvent


class MessageEndEvent(BaseModel):
    """Message end event."""

    model_config = ConfigDict(extra="forbid")
    type: Literal["message_end"] = "message_end"
    message: AgentMessage


class ToolExecutionStartEvent(BaseModel):
    """Tool execution start event."""

    model_config = ConfigDict(extra="forbid")
    type: Literal["tool_execution_start"] = "tool_execution_start"
    tool_call_id: str
    tool_name: str
    args: Any


class ToolExecutionUpdateEvent(BaseModel):
    """Tool execution update event."""

    model_config = ConfigDict(extra="forbid")
    type: Literal["tool_execution_update"] = "tool_execution_update"
    tool_call_id: str
    tool_name: str
    args: Any
    partial_result: Any


class ToolExecutionEndEvent(BaseModel):
    """Tool execution end event."""

    model_config = ConfigDict(extra="forbid")
    type: Literal["tool_execution_end"] = "tool_execution_end"
    tool_call_id: str
    tool_name: str
    result: Any
    is_error: bool


AgentEvent: TypeAlias = (
    AgentStartEvent
    | AgentEndEvent
    | TurnStartEvent
    | TurnEndEvent
    | MessageStartEvent
    | MessageUpdateEvent
    | MessageEndEvent
    | ToolExecutionStartEvent
    | ToolExecutionUpdateEvent
    | ToolExecutionEndEvent
)
