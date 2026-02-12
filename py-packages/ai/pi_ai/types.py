"""
Core types for pi-ai.
"""

from __future__ import annotations

from typing import Any, Callable, Literal, Protocol, TypeAlias, TypeVar

from pydantic import BaseModel, ConfigDict, Field

# API Types
KnownApi: TypeAlias = Literal[
    "openai-completions",
    "openai-responses",
    "azure-openai-responses",
    "openai-codex-responses",
    "anthropic-messages",
    "bedrock-converse-stream",
    "google-generative-ai",
    "google-gemini-cli",
    "google-vertex",
]

Api: TypeAlias = KnownApi | str

KnownProvider: TypeAlias = Literal[
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
    "kimi-coding",
]

Provider: TypeAlias = KnownProvider | str

ThinkingLevel: TypeAlias = Literal["minimal", "low", "medium", "high", "xhigh"]

StopReason: TypeAlias = Literal["stop", "length", "toolUse", "error", "aborted"]

CacheRetention: TypeAlias = Literal["none", "short", "long"]

InputType: TypeAlias = Literal["text", "image"]


class ThinkingBudgets(BaseModel):
    """Token budgets for each thinking level (token-based providers only)."""

    model_config = ConfigDict(extra="forbid")

    minimal: int | None = None
    low: int | None = None
    medium: int | None = None
    high: int | None = None


class StreamOptions(BaseModel):
    """Base options all providers share."""

    model_config = ConfigDict(extra="allow")

    temperature: float | None = None
    max_tokens: int | None = None
    api_key: str | None = None
    cache_retention: CacheRetention | None = None
    session_id: str | None = None
    headers: dict[str, str] | None = None
    max_retry_delay_ms: int | None = None
    # Note: signal is handled differently in Python (via asyncio cancellation)
    # Note: on_payload callback is handled via method override


class SimpleStreamOptions(StreamOptions):
    """Unified options with reasoning passed to stream_simple() and complete_simple()."""

    reasoning: ThinkingLevel | None = None
    thinking_budgets: ThinkingBudgets | None = None


class TextContent(BaseModel):
    """Text content block."""

    model_config = ConfigDict(extra="forbid")

    type: Literal["text"] = "text"
    text: str
    text_signature: str | None = None


class ThinkingContent(BaseModel):
    """Thinking/reasoning content block."""

    model_config = ConfigDict(extra="forbid")

    type: Literal["thinking"] = "thinking"
    thinking: str
    thinking_signature: str | None = None


class ImageContent(BaseModel):
    """Image content block."""

    model_config = ConfigDict(extra="forbid")

    type: Literal["image"] = "image"
    data: str  # base64 encoded image data
    mime_type: str  # e.g., "image/jpeg", "image/png"


class ToolCall(BaseModel):
    """Tool call content block."""

    model_config = ConfigDict(extra="forbid")

    type: Literal["toolCall"] = "toolCall"
    id: str
    name: str
    arguments: dict[str, Any] = Field(default_factory=dict)
    thought_signature: str | None = None  # Google-specific


class UsageCost(BaseModel):
    """Cost breakdown for a message."""

    model_config = ConfigDict(extra="forbid")

    input: float = 0.0
    output: float = 0.0
    cache_read: float = 0.0
    cache_write: float = 0.0
    total: float = 0.0


class Usage(BaseModel):
    """Token usage information."""

    model_config = ConfigDict(extra="forbid")

    input: int = 0
    output: int = 0
    cache_read: int = 0
    cache_write: int = 0
    total_tokens: int = 0
    cost: UsageCost = Field(default_factory=UsageCost)


class UserMessage(BaseModel):
    """User message."""

    model_config = ConfigDict(extra="forbid")

    role: Literal["user"] = "user"
    content: str | list[TextContent | ImageContent]
    timestamp: int  # Unix timestamp in milliseconds


class AssistantMessage(BaseModel):
    """Assistant message."""

    model_config = ConfigDict(extra="forbid")

    role: Literal["assistant"] = "assistant"
    content: list[TextContent | ThinkingContent | ToolCall] = Field(default_factory=list)
    api: Api
    provider: Provider
    model: str
    usage: Usage = Field(default_factory=Usage)
    stop_reason: StopReason = "stop"
    error_message: str | None = None
    timestamp: int  # Unix timestamp in milliseconds


class ToolResultMessage(BaseModel):
    """Tool result message."""

    model_config = ConfigDict(extra="allow")

    role: Literal["toolResult"] = "toolResult"
    tool_call_id: str
    tool_name: str
    content: list[TextContent | ImageContent]
    details: Any = None
    is_error: bool = False
    timestamp: int  # Unix timestamp in milliseconds


Message: TypeAlias = UserMessage | AssistantMessage | ToolResultMessage


class Tool(BaseModel):
    """Tool definition."""

    model_config = ConfigDict(extra="forbid")

    name: str
    description: str
    parameters: dict[str, Any]  # JSON Schema


class Context(BaseModel):
    """Conversation context for LLM calls."""

    model_config = ConfigDict(extra="forbid")

    system_prompt: str | None = None
    messages: list[Message] = Field(default_factory=list)
    tools: list[Tool] | None = None


# Assistant Message Events
class StartEvent(BaseModel):
    """Start of assistant message."""

    model_config = ConfigDict(extra="forbid")

    type: Literal["start"] = "start"
    partial: AssistantMessage


class TextStartEvent(BaseModel):
    """Start of text content block."""

    model_config = ConfigDict(extra="forbid")

    type: Literal["text_start"] = "text_start"
    content_index: int
    partial: AssistantMessage


class TextDeltaEvent(BaseModel):
    """Text content delta."""

    model_config = ConfigDict(extra="forbid")

    type: Literal["text_delta"] = "text_delta"
    content_index: int
    delta: str
    partial: AssistantMessage


class TextEndEvent(BaseModel):
    """End of text content block."""

    model_config = ConfigDict(extra="forbid")

    type: Literal["text_end"] = "text_end"
    content_index: int
    content: str
    partial: AssistantMessage


class ThinkingStartEvent(BaseModel):
    """Start of thinking content block."""

    model_config = ConfigDict(extra="forbid")

    type: Literal["thinking_start"] = "thinking_start"
    content_index: int
    partial: AssistantMessage


class ThinkingDeltaEvent(BaseModel):
    """Thinking content delta."""

    model_config = ConfigDict(extra="forbid")

    type: Literal["thinking_delta"] = "thinking_delta"
    content_index: int
    delta: str
    partial: AssistantMessage


class ThinkingEndEvent(BaseModel):
    """End of thinking content block."""

    model_config = ConfigDict(extra="forbid")

    type: Literal["thinking_end"] = "thinking_end"
    content_index: int
    content: str
    partial: AssistantMessage


class ToolCallStartEvent(BaseModel):
    """Start of tool call content block."""

    model_config = ConfigDict(extra="forbid")

    type: Literal["toolcall_start"] = "toolcall_start"
    content_index: int
    partial: AssistantMessage


class ToolCallDeltaEvent(BaseModel):
    """Tool call arguments delta."""

    model_config = ConfigDict(extra="forbid")

    type: Literal["toolcall_delta"] = "toolcall_delta"
    content_index: int
    delta: str
    partial: AssistantMessage


class ToolCallEndEvent(BaseModel):
    """End of tool call content block."""

    model_config = ConfigDict(extra="forbid")

    type: Literal["toolcall_end"] = "toolcall_end"
    content_index: int
    tool_call: ToolCall
    partial: AssistantMessage


class DoneEvent(BaseModel):
    """Successful completion of assistant message."""

    model_config = ConfigDict(extra="forbid")

    type: Literal["done"] = "done"
    reason: Literal["stop", "length", "toolUse"]
    message: AssistantMessage


class ErrorEvent(BaseModel):
    """Error during assistant message generation."""

    model_config = ConfigDict(extra="forbid")

    type: Literal["error"] = "error"
    reason: Literal["aborted", "error"]
    error: AssistantMessage


AssistantMessageEvent: TypeAlias = (
    StartEvent
    | TextStartEvent
    | TextDeltaEvent
    | TextEndEvent
    | ThinkingStartEvent
    | ThinkingDeltaEvent
    | ThinkingEndEvent
    | ToolCallStartEvent
    | ToolCallDeltaEvent
    | ToolCallEndEvent
    | DoneEvent
    | ErrorEvent
)


class OpenRouterRouting(BaseModel):
    """OpenRouter provider routing preferences."""

    model_config = ConfigDict(extra="forbid")

    only: list[str] | None = None
    order: list[str] | None = None


class VercelGatewayRouting(BaseModel):
    """Vercel AI Gateway routing preferences."""

    model_config = ConfigDict(extra="forbid")

    only: list[str] | None = None
    order: list[str] | None = None


class OpenAICompletionsCompat(BaseModel):
    """Compatibility settings for OpenAI-compatible completions APIs."""

    model_config = ConfigDict(extra="forbid")

    supports_store: bool | None = None
    supports_developer_role: bool | None = None
    supports_reasoning_effort: bool | None = None
    supports_usage_in_streaming: bool | None = None
    max_tokens_field: Literal["max_completion_tokens", "max_tokens"] | None = None
    requires_tool_result_name: bool | None = None
    requires_assistant_after_tool_result: bool | None = None
    requires_thinking_as_text: bool | None = None
    requires_mistral_tool_ids: bool | None = None
    thinking_format: Literal["openai", "zai", "qwen"] | None = None
    open_router_routing: OpenRouterRouting | None = None
    vercel_gateway_routing: VercelGatewayRouting | None = None
    supports_strict_mode: bool | None = None


class OpenAIResponsesCompat(BaseModel):
    """Compatibility settings for OpenAI Responses APIs."""

    model_config = ConfigDict(extra="forbid")
    # Reserved for future use


class ModelCost(BaseModel):
    """Cost per million tokens."""

    model_config = ConfigDict(extra="forbid")

    input: float  # $/million tokens
    output: float  # $/million tokens
    cache_read: float  # $/million tokens
    cache_write: float  # $/million tokens


TApi = TypeVar("TApi", bound=Api)


class Model(BaseModel):
    """Model definition."""

    model_config = ConfigDict(extra="forbid")

    id: str
    name: str
    api: Api
    provider: Provider
    base_url: str
    reasoning: bool
    input: list[InputType]
    cost: ModelCost
    context_window: int
    max_tokens: int
    headers: dict[str, str] | None = None
    compat: OpenAICompletionsCompat | OpenAIResponsesCompat | None = None


# Stream function types
class StreamFunction(Protocol[TApi]):
    """Protocol for stream functions."""

    def __call__(
        self,
        model: Model,
        context: Context,
        options: StreamOptions | None = None,
    ) -> "AssistantMessageEventStream":
        ...


# Forward reference for AssistantMessageEventStream
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pi_ai.event_stream import AssistantMessageEventStream
