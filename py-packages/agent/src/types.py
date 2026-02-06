"""
Type definitions for the Agent package.
"""

from typing import (
    Any,
    Callable,
    Dict,
    List,
    Literal,
    Optional,
    Protocol,
    Set,
    Tuple,
    TypeVar,
    Union,
)
from dataclasses import dataclass, field
from abc import ABC, abstractmethod
import asyncio

# Thinking level types
ThinkingLevel = Literal["off", "minimal", "low", "medium", "high", "xhigh"]

# Base message types that would come from pi-ai package
@dataclass
class TextContent:
    type: Literal["text"] = "text"
    text: str = ""

@dataclass
class ImageContent:
    type: Literal["image"] = "image"
    data: str = ""
    mimeType: str = ""

@dataclass
class ToolCall:
    type: Literal["toolCall"] = "toolCall"
    id: str = ""
    name: str = ""
    arguments: Dict[str, Any] = field(default_factory=dict)

@dataclass
class ThinkingContent:
    type: Literal["thinking"] = "thinking"
    thinking: str = ""

ContentType = Union[TextContent, ImageContent, ToolCall, ThinkingContent]

@dataclass
class Usage:
    input: int = 0
    output: int = 0
    cacheRead: int = 0
    cacheWrite: int = 0
    totalTokens: int = 0
    cost: 'Usage.Cost' = field(default_factory=lambda: Usage.Cost())
    
    @dataclass
    class Cost:
        input: float = 0.0
        output: float = 0.0
        cacheRead: float = 0.0
        cacheWrite: float = 0.0
        total: float = 0.0

@dataclass
class BaseMessage:
    role: str
    content: List[ContentType] = field(default_factory=list)
    timestamp: int = 0

@dataclass
class UserMessage(BaseMessage):
    role: Literal["user"] = "user"

@dataclass
class AssistantMessage(BaseMessage):
    role: Literal["assistant"] = "assistant"
    api: str = ""
    provider: str = ""
    model: str = ""
    usage: Usage = field(default_factory=Usage)
    stopReason: str = "stop"
    errorMessage: Optional[str] = None

@dataclass
class ToolResultMessage(BaseMessage):
    role: Literal["toolResult"] = "toolResult"
    toolCallId: str = ""
    toolName: str = ""
    details: Dict[str, Any] = field(default_factory=dict)
    isError: bool = False

Message = Union[UserMessage, AssistantMessage, ToolResultMessage]

# Agent-specific types
class CustomAgentMessages(Protocol):
    """Extensible interface for custom app messages."""
    pass

# AgentMessage can be any Message or custom message types
AgentMessage = Union[Message, CustomAgentMessages]

@dataclass
class AgentToolResult:
    content: List[Union[TextContent, ImageContent]]
    details: Dict[str, Any]

# Tool callback type
AgentToolUpdateCallback = Callable[[AgentToolResult], None]

# Schema-like type for tool parameters
TParameters = TypeVar('TParameters', bound=Dict[str, Any])

@dataclass
class Tool:
    name: str
    description: str
    parameters: TParameters

@dataclass
class AgentTool(Tool):
    label: str
    execute: Callable[
        [str, Dict[str, Any], Optional[asyncio.Event], Optional[AgentToolUpdateCallback]], 
        asyncio.Future[AgentToolResult]
    ]

@dataclass
class AgentContext:
    systemPrompt: str
    messages: List[AgentMessage]
    tools: Optional[List[AgentTool]] = field(default=None)

@dataclass
class AgentState:
    systemPrompt: str = ""
    model: Any = None  # Would be Model type from pi-ai
    thinkingLevel: ThinkingLevel = "off"
    tools: List[AgentTool] = field(default_factory=list)
    messages: List[AgentMessage] = field(default_factory=list)
    isStreaming: bool = False
    streamMessage: Optional[AgentMessage] = None
    pendingToolCalls: Set[str] = field(default_factory=set)
    error: Optional[str] = None

# Event types
@dataclass
class AgentStartEvent:
    type: Literal["agent_start"] = "agent_start"

@dataclass
class AgentEndEvent:
    type: Literal["agent_end"] = "agent_end"
    messages: List[AgentMessage] = field(default_factory=list)

@dataclass
class TurnStartEvent:
    type: Literal["turn_start"] = "turn_start"

@dataclass
class TurnEndEvent:
    type: Literal["turn_end"] = "turn_end"
    message: AgentMessage = field(default=None)  # type: ignore
    toolResults: List[ToolResultMessage] = field(default_factory=list)

@dataclass
class MessageStartEvent:
    type: Literal["message_start"] = "message_start"
    message: AgentMessage

@dataclass
class AssistantMessageEvent:
    type: str
    partial: AssistantMessage

@dataclass
class MessageUpdateEvent:
    type: Literal["message_update"] = "message_update"
    message: AgentMessage
    assistantMessageEvent: AssistantMessageEvent

@dataclass
class MessageEndEvent:
    type: Literal["message_end"] = "message_end"
    message: AgentMessage

@dataclass
class ToolExecutionStartEvent:
    type: Literal["tool_execution_start"] = "tool_execution_start"
    toolCallId: str
    toolName: str
    args: Dict[str, Any]

@dataclass
class ToolExecutionUpdateEvent:
    type: Literal["tool_execution_update"] = "tool_execution_update"
    toolCallId: str
    toolName: str
    args: Dict[str, Any]
    partialResult: Any

@dataclass
class ToolExecutionEndEvent:
    type: Literal["tool_execution_end"] = "tool_execution_end"
    toolCallId: str
    toolName: str
    result: Any
    isError: bool

AgentEvent = Union[
    AgentStartEvent,
    AgentEndEvent,
    TurnStartEvent,
    TurnEndEvent,
    MessageStartEvent,
    MessageUpdateEvent,
    MessageEndEvent,
    ToolExecutionStartEvent,
    ToolExecutionUpdateEvent,
    ToolExecutionEndEvent,
]

# Configuration types
class AgentLoopConfig:
    def __init__(
        self,
        model: Any,  # Model type from pi-ai
        convert_to_llm: Callable[[List[AgentMessage]], Union[List[Message], asyncio.Future[List[Message]]]],
        transform_context: Optional[Callable[[List[AgentMessage], Optional[asyncio.Event]], asyncio.Future[List[AgentMessage]]]] = None,
        get_api_key: Optional[Callable[[str], Union[str, asyncio.Future[str], None]]] = None,
        get_steering_messages: Optional[Callable[[], asyncio.Future[List[AgentMessage]]]] = None,
        get_follow_up_messages: Optional[Callable[[], asyncio.Future[List[AgentMessage]]]] = None,
    ):
        self.model = model
        self.convert_to_llm = convert_to_llm
        self.transform_context = transform_context
        self.get_api_key = get_api_key
        self.get_steering_messages = get_steering_messages
        self.get_follow_up_messages = get_follow_up_messages

# Stream function type
StreamFn = Callable[..., Any]  # Simplified - would match pi-ai stream function signature