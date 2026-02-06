"""
Data models for session entries and messages
"""
from typing import List, Optional, Union, Dict, Any
from datetime import datetime
from enum import Enum
from pydantic import BaseModel, Field
import uuid


class MessageType(str, Enum):
    USER = "user"
    ASSISTANT = "assistant"
    TOOL_RESULT = "toolResult"
    BASH_EXECUTION = "bashExecution"
    CUSTOM = "custom"
    BRANCH_SUMMARY = "branchSummary"
    COMPACTION_SUMMARY = "compactionSummary"


class ThinkingLevel(str, Enum):
    OFF = "off"
    MINIMAL = "minimal"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    XHIGH = "xhigh"


class TextContent(BaseModel):
    type: str = "text"
    text: str


class ImageContent(BaseModel):
    type: str = "image"
    data: str  # base64 encoded
    mime_type: str


class ThinkingContent(BaseModel):
    type: str = "thinking"
    thinking: str


class ToolCall(BaseModel):
    type: str = "toolCall"
    id: str
    name: str
    arguments: Dict[str, Any]


class Usage(BaseModel):
    input: int = 0
    output: int = 0
    cache_read: int = 0
    cache_write: int = 0
    total_tokens: int = 0
    cost: Dict[str, float] = Field(default_factory=lambda: {
        "input": 0.0,
        "output": 0.0,
        "cache_read": 0.0,
        "cache_write": 0.0,
        "total": 0.0
    })


class BaseMessage(BaseModel):
    role: MessageType
    timestamp: datetime = Field(default_factory=datetime.now)
    content: Union[str, List[Union[TextContent, ImageContent]]]


class UserMessage(BaseMessage):
    role: MessageType = MessageType.USER


class AssistantMessage(BaseMessage):
    role: MessageType = MessageType.ASSISTANT
    api: str
    provider: str
    model: str
    usage: Usage
    stop_reason: str
    error_message: Optional[str] = None


class ToolResultMessage(BaseMessage):
    role: MessageType = MessageType.TOOL_RESULT
    tool_call_id: str
    tool_name: str
    is_error: bool = False
    details: Optional[Any] = None


class BashExecutionMessage(BaseMessage):
    role: MessageType = MessageType.BASH_EXECUTION
    command: str
    output: str
    exit_code: Optional[int] = None
    cancelled: bool = False
    truncated: bool = False
    full_output_path: Optional[str] = None
    exclude_from_context: bool = False


class CustomMessage(BaseMessage):
    role: MessageType = MessageType.CUSTOM
    custom_type: str
    display: bool = True
    details: Optional[Any] = None


class BranchSummaryMessage(BaseMessage):
    role: MessageType = MessageType.BRANCH_SUMMARY
    summary: str
    from_id: str


class CompactionSummaryMessage(BaseMessage):
    role: MessageType = MessageType.COMPACTION_SUMMARY
    summary: str
    tokens_before: int


# Union type for all message types
AgentMessage = Union[
    UserMessage,
    AssistantMessage,
    ToolResultMessage,
    BashExecutionMessage,
    CustomMessage,
    BranchSummaryMessage,
    CompactionSummaryMessage
]


class SessionHeader(BaseModel):
    type: str = "session"
    version: int = 3
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: datetime = Field(default_factory=datetime.now)
    cwd: str
    parent_session: Optional[str] = None


class SessionEntryBase(BaseModel):
    type: str
    id: str = Field(default_factory=lambda: uuid.uuid4().hex[:8])
    parent_id: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.now)


class SessionMessageEntry(SessionEntryBase):
    type: str = "message"
    message: AgentMessage


class ThinkingLevelChangeEntry(SessionEntryBase):
    type: str = "thinking_level_change"
    thinking_level: ThinkingLevel


class ModelChangeEntry(SessionEntryBase):
    type: str = "model_change"
    provider: str
    model_id: str


class CompactionEntry(SessionEntryBase):
    type: str = "compaction"
    summary: str
    first_kept_entry_id: str
    tokens_before: int
    details: Optional[Dict[str, Any]] = None
    from_hook: Optional[bool] = None


class BranchSummaryEntry(SessionEntryBase):
    type: str = "branch_summary"
    from_id: str
    summary: str
    details: Optional[Dict[str, Any]] = None
    from_hook: Optional[bool] = None


class CustomEntry(SessionEntryBase):
    type: str = "custom"
    custom_type: str
    data: Optional[Any] = None


class LabelEntry(SessionEntryBase):
    type: str = "label"
    target_id: str
    label: Optional[str] = None


class SessionInfoEntry(SessionEntryBase):
    type: str = "session_info"
    name: Optional[str] = None


class CustomMessageEntry(SessionEntryBase):
    type: str = "custom_message"
    custom_type: str
    content: Union[str, List[Union[TextContent, ImageContent]]]
    details: Optional[Any] = None
    display: bool = True


# Union of all session entry types
SessionEntry = Union[
    SessionMessageEntry,
    ThinkingLevelChangeEntry,
    ModelChangeEntry,
    CompactionEntry,
    BranchSummaryEntry,
    CustomEntry,
    CustomMessageEntry,
    LabelEntry,
    SessionInfoEntry
]


class SessionContext(BaseModel):
    messages: List[AgentMessage]
    thinking_level: ThinkingLevel = ThinkingLevel.OFF
    model: Optional[Dict[str, str]] = None