"""
Core types for the AI package.
"""

from typing import (
    Any,
    Dict,
    List,
    Literal,
    Optional,
    Protocol,
    TypedDict,
    Union,
    runtime_checkable
)
from dataclasses import dataclass, field
from abc import ABC, abstractmethod
import asyncio

# Forward references for circular imports
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from .utils.event_stream import AssistantMessageEventStream

# API and Provider types
KnownApi = Literal[
    "openai-completions",
    "openai-responses", 
    "azure-openai-responses",
    "openai-codex-responses",
    "anthropic-messages",
    "bedrock-converse-stream",
    "google-generative-ai",
    "google-gemini-cli",
    "google-vertex"
]

Api = Union[KnownApi, str]

KnownProvider = Literal[
    "amazon-bedrock",
    "anthropic", 
    "google",
    "google-gemini-cli",
    "google-antigravity",
    "google-vertex",
    "openai",
    "azure-openai-responses",
    "openai-codex",
    "github-copilot",
    "xai",
    "groq",
    "cerebras",
    "openrouter",
    "vercel-ai-gateway",
    "zai",
    "mistral",
    "minimax",
    "minimax-cn",
    "huggingface",
    "opencode",
    "kimi-coding"
]

Provider = Union[KnownProvider, str]

# Thinking levels
ThinkingLevel = Literal["minimal", "low", "medium", "high", "xhigh"]

@dataclass
class ThinkingBudgets:
    minimal: Optional[int] = None
    low: Optional[int] = None
    medium: Optional[int] = None
    high: Optional[int] = None

# Cache retention
CacheRetention = Literal["none", "short", "long"]

# Base content types
@dataclass
class TextContent:
    type: Literal["text"] = "text"
    text: str = ""
    text_signature: Optional[str] = None

@dataclass
class ThinkingContent:
    type: Literal["thinking"] = "thinking"
    thinking: str = ""
    thinking_signature: Optional[str] = None

@dataclass
class ImageContent:
    type: Literal["image"] = "image"
    data: str = ""  # base64 encoded image data
    mime_type: str = ""  # e.g., "image/jpeg", "image/png"

@dataclass
class ToolCall:
    type: Literal["toolCall"] = "toolCall"
    id: str = ""
    name: str = ""
    arguments: Dict[str, Any] = field(default_factory=dict)
    thought_signature: Optional[str] = None  # Google-specific

# Usage tracking
@dataclass
class UsageCost:
    input: float = 0.0
    output: float = 0.0
    cache_read: float = 0.0
    cache_write: float = 0.0
    total: float = 0.0

@dataclass
class Usage:
    input: int = 0
    output: int = 0
    cache_read: int = 0
    cache_write: int = 0
    total_tokens: int = 0
    cost: UsageCost = field(default_factory=UsageCost)

# Stop reasons
StopReason = Literal["stop", "length", "toolUse", "error", "aborted"]

# Message types
@dataclass
class UserMessage:
    role: Literal["user"] = "user"
    content: Union[str, List[Union[TextContent, ImageContent]]] = ""
    timestamp: int = 0  # Unix timestamp in milliseconds

@dataclass
class AssistantMessage:
    role: Literal["assistant"] = "assistant"
    content: List[Union[TextContent, ThinkingContent, ToolCall]] = field(default_factory=list)
    api: Api = ""
    provider: Provider = ""
    model: str = ""
    usage: Usage = field(default_factory=Usage)
    stop_reason: StopReason = "stop"
    error_message: Optional[str] = None
    timestamp: int = 0  # Unix timestamp in milliseconds

@dataclass
class ToolResultMessage:
    role: Literal["toolResult"] = "toolResult"
    tool_call_id: str = ""
    tool_name: str = ""
    content: List[Union[TextContent, ImageContent]] = field(default_factory=list)
    details: Optional[Dict[str, Any]] = None
    is_error: bool = False
    timestamp: int = 0  # Unix timestamp in milliseconds

Message = Union[UserMessage, AssistantMessage, ToolResultMessage]

# Tool definition
@runtime_checkable
class Tool(Protocol):
    name: str
    description: str
    parameters: Dict[str, Any]

@dataclass
class Context:
    system_prompt: Optional[str] = None
    messages: List[Message] = field(default_factory=list)
    tools: Optional[List[Tool]] = None

# Stream options
@dataclass
class StreamOptions:
    temperature: Optional[float] = None
    max_tokens: Optional[int] = None
    signal: Optional[asyncio.Event] = None
    api_key: Optional[str] = None
    cache_retention: CacheRetention = "short"
    session_id: Optional[str] = None
    on_payload: Optional[callable] = None  # type: ignore
    headers: Optional[Dict[str, str]] = None
    max_retry_delay_ms: Optional[int] = None

@dataclass
class SimpleStreamOptions(StreamOptions):
    reasoning: Optional[ThinkingLevel] = None
    thinking_budgets: Optional[ThinkingBudgets] = None

ProviderStreamOptions = StreamOptions

# Event types for streaming
@dataclass
class StartEvent:
    type: Literal["start"] = "start"
    partial: AssistantMessage = None  # type: ignore

@dataclass
class TextStartEvent:
    type: Literal["text_start"] = "text_start"
    content_index: int = 0
    partial: AssistantMessage = None  # type: ignore

@dataclass
class TextDeltaEvent:
    type: Literal["text_delta"] = "text_delta"
    content_index: int = 0
    delta: str = ""
    partial: AssistantMessage = None  # type: ignore

@dataclass
class TextEndEvent:
    type: Literal["text_end"] = "text_end"
    content_index: int = 0
    content: str = ""
    partial: AssistantMessage = None  # type: ignore

@dataclass
class ThinkingStartEvent:
    type: Literal["thinking_start"] = "thinking_start"
    content_index: int = 0
    partial: AssistantMessage = None  # type: ignore

@dataclass
class ThinkingDeltaEvent:
    type: Literal["thinking_delta"] = "thinking_delta"
    content_index: int = 0
    delta: str = ""
    partial: AssistantMessage = None  # type: ignore

@dataclass
class ThinkingEndEvent:
    type: Literal["thinking_end"] = "thinking_end"
    content_index: int = 0
    content: str = ""
    partial: AssistantMessage = None  # type: ignore

@dataclass
class ToolCallStartEvent:
    type: Literal["toolcall_start"] = "toolcall_start"
    content_index: int = 0
    partial: AssistantMessage = None  # type: ignore

@dataclass
class ToolCallDeltaEvent:
    type: Literal["toolcall_delta"] = "toolcall_delta"
    content_index: int = 0
    delta: str = ""
    partial: AssistantMessage = None  # type: ignore

@dataclass
class ToolCallEndEvent:
    type: Literal["toolcall_end"] = "toolcall_end"
    content_index: int = 0
    tool_call: ToolCall = None  # type: ignore
    partial: AssistantMessage = None  # type: ignore

@dataclass
class DoneEvent:
    type: Literal["done"] = "done"
    reason: Literal["stop", "length", "toolUse"] = "stop"
    message: AssistantMessage = None  # type: ignore

@dataclass
class ErrorEvent:
    type: Literal["error"] = "error"
    reason: Literal["aborted", "error"] = "error"
    error: AssistantMessage = None  # type: ignore

AssistantMessageEvent = Union[
    StartEvent,
    TextStartEvent,
    TextDeltaEvent,
    TextEndEvent,
    ThinkingStartEvent,
    ThinkingDeltaEvent,
    ThinkingEndEvent,
    ToolCallStartEvent,
    ToolCallDeltaEvent,
    ToolCallEndEvent,
    DoneEvent,
    ErrorEvent
]

# Compatibility settings
@dataclass
class OpenRouterRouting:
    only: Optional[List[str]] = None
    order: Optional[List[str]] = None

@dataclass
class VercelGatewayRouting:
    only: Optional[List[str]] = None
    order: Optional[List[str]] = None

@dataclass
class OpenAICompletionsCompat:
    supports_store: Optional[bool] = None
    supports_developer_role: Optional[bool] = None
    supports_reasoning_effort: Optional[bool] = None
    supports_usage_in_streaming: bool = True
    max_tokens_field: Optional[Literal["max_completion_tokens", "max_tokens"]] = None
    requires_tool_result_name: Optional[bool] = None
    requires_assistant_after_tool_result: Optional[bool] = None
    requires_thinking_as_text: Optional[bool] = None
    requires_mistral_tool_ids: Optional[bool] = None
    thinking_format: Literal["openai", "zai", "qwen"] = "openai"
    open_router_routing: Optional[OpenRouterRouting] = None
    vercel_gateway_routing: Optional[VercelGatewayRouting] = None
    supports_strict_mode: bool = True

@dataclass
class OpenAIResponsesCompat:
    pass

# Model definition
@dataclass
class Model:
    id: str
    name: str
    api: Api
    provider: Provider
    base_url: str
    reasoning: bool
    input: List[Literal["text", "image"]]
    cost: UsageCost
    context_window: int
    max_tokens: int
    headers: Optional[Dict[str, str]] = None
    compat: Optional[Union[OpenAICompletionsCompat, OpenAIResponsesCompat]] = None

# Stream function type
StreamFunction = callable  # type: ignore