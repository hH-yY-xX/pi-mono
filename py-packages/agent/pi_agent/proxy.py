"""
Proxy stream function for apps that route LLM calls through a server.
"""

from __future__ import annotations

import asyncio
import json
import time
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict

from pi_ai import (
    AssistantMessage,
    AssistantMessageEvent,
    Context,
    EventStream,
    Model,
    SimpleStreamOptions,
    StopReason,
    TextContent,
    ThinkingContent,
    ToolCall,
    Usage,
    UsageCost,
    parse_streaming_json,
)


class ProxyMessageEventStream(EventStream[AssistantMessageEvent, AssistantMessage]):
    """Event stream for proxy responses."""

    def __init__(self) -> None:
        super().__init__(
            is_complete=lambda event: event.type in ("done", "error"),
            extract_result=lambda event: (
                event.message if event.type == "done" else
                event.error if event.type == "error" else None
            ),
        )


class ProxyStartEvent(BaseModel):
    """Proxy start event."""

    model_config = ConfigDict(extra="forbid")
    type: Literal["start"] = "start"


class ProxyTextStartEvent(BaseModel):
    """Proxy text start event."""

    model_config = ConfigDict(extra="forbid")
    type: Literal["text_start"] = "text_start"
    content_index: int


class ProxyTextDeltaEvent(BaseModel):
    """Proxy text delta event."""

    model_config = ConfigDict(extra="forbid")
    type: Literal["text_delta"] = "text_delta"
    content_index: int
    delta: str


class ProxyTextEndEvent(BaseModel):
    """Proxy text end event."""

    model_config = ConfigDict(extra="forbid")
    type: Literal["text_end"] = "text_end"
    content_index: int
    content_signature: str | None = None


class ProxyThinkingStartEvent(BaseModel):
    """Proxy thinking start event."""

    model_config = ConfigDict(extra="forbid")
    type: Literal["thinking_start"] = "thinking_start"
    content_index: int


class ProxyThinkingDeltaEvent(BaseModel):
    """Proxy thinking delta event."""

    model_config = ConfigDict(extra="forbid")
    type: Literal["thinking_delta"] = "thinking_delta"
    content_index: int
    delta: str


class ProxyThinkingEndEvent(BaseModel):
    """Proxy thinking end event."""

    model_config = ConfigDict(extra="forbid")
    type: Literal["thinking_end"] = "thinking_end"
    content_index: int
    content_signature: str | None = None


class ProxyToolCallStartEvent(BaseModel):
    """Proxy tool call start event."""

    model_config = ConfigDict(extra="forbid")
    type: Literal["toolcall_start"] = "toolcall_start"
    content_index: int
    id: str
    tool_name: str


class ProxyToolCallDeltaEvent(BaseModel):
    """Proxy tool call delta event."""

    model_config = ConfigDict(extra="forbid")
    type: Literal["toolcall_delta"] = "toolcall_delta"
    content_index: int
    delta: str


class ProxyToolCallEndEvent(BaseModel):
    """Proxy tool call end event."""

    model_config = ConfigDict(extra="forbid")
    type: Literal["toolcall_end"] = "toolcall_end"
    content_index: int


class ProxyDoneEvent(BaseModel):
    """Proxy done event."""

    model_config = ConfigDict(extra="forbid")
    type: Literal["done"] = "done"
    reason: Literal["stop", "length", "toolUse"]
    usage: Usage


class ProxyErrorEvent(BaseModel):
    """Proxy error event."""

    model_config = ConfigDict(extra="forbid")
    type: Literal["error"] = "error"
    reason: Literal["aborted", "error"]
    error_message: str | None = None
    usage: Usage


ProxyAssistantMessageEvent = (
    ProxyStartEvent
    | ProxyTextStartEvent
    | ProxyTextDeltaEvent
    | ProxyTextEndEvent
    | ProxyThinkingStartEvent
    | ProxyThinkingDeltaEvent
    | ProxyThinkingEndEvent
    | ProxyToolCallStartEvent
    | ProxyToolCallDeltaEvent
    | ProxyToolCallEndEvent
    | ProxyDoneEvent
    | ProxyErrorEvent
)


class ProxyStreamOptions(SimpleStreamOptions):
    """Options for proxy streaming."""

    auth_token: str
    """Auth token for the proxy server."""

    proxy_url: str
    """Proxy server URL."""


def stream_proxy(
    model: Model,
    context: Context,
    options: ProxyStreamOptions,
) -> ProxyMessageEventStream:
    """
    Stream function that proxies through a server.
    
    The server strips the partial field from delta events to reduce bandwidth.
    We reconstruct the partial message client-side.
    """
    stream = ProxyMessageEventStream()

    async def _run() -> None:
        # Initialize the partial message
        partial = AssistantMessage(
            role="assistant",
            content=[],
            api=model.api,
            provider=model.provider,
            model=model.id,
            usage=Usage(),
            stop_reason="stop",
            timestamp=int(time.time() * 1000),
        )

        try:
            import httpx

            async with httpx.AsyncClient() as client:
                async with client.stream(
                    "POST",
                    f"{options.proxy_url}/api/stream",
                    headers={
                        "Authorization": f"Bearer {options.auth_token}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": model.model_dump(),
                        "context": context.model_dump(),
                        "options": {
                            "temperature": options.temperature,
                            "max_tokens": options.max_tokens,
                            "reasoning": options.reasoning,
                        },
                    },
                    timeout=300.0,
                ) as response:
                    if response.status_code != 200:
                        error_message = f"Proxy error: {response.status_code}"
                        try:
                            error_data = await response.json()
                            if error_data.get("error"):
                                error_message = f"Proxy error: {error_data['error']}"
                        except Exception:
                            pass
                        raise RuntimeError(error_message)

                    buffer = ""
                    async for chunk in response.aiter_text():
                        buffer += chunk
                        lines = buffer.split("\n")
                        buffer = lines.pop()

                        for line in lines:
                            if line.startswith("data: "):
                                data = line[6:].strip()
                                if data:
                                    proxy_event = json.loads(data)
                                    event = _process_proxy_event(proxy_event, partial)
                                    if event:
                                        stream.push(event)

            stream.end()

        except Exception as e:
            error_message = str(e)
            partial.stop_reason = "error"
            partial.error_message = error_message
            stream.push({
                "type": "error",
                "reason": "error",
                "error": partial,
            })
            stream.end()

    asyncio.get_event_loop().create_task(_run())
    return stream


def _process_proxy_event(
    proxy_event: dict[str, Any],
    partial: AssistantMessage,
) -> AssistantMessageEvent | None:
    """Process a proxy event and update the partial message."""
    event_type = proxy_event.get("type")

    if event_type == "start":
        return {"type": "start", "partial": partial}

    elif event_type == "text_start":
        content_index = proxy_event["content_index"]
        partial.content.insert(content_index, TextContent(type="text", text=""))
        return {"type": "text_start", "content_index": content_index, "partial": partial}

    elif event_type == "text_delta":
        content_index = proxy_event["content_index"]
        content = partial.content[content_index]
        if content.type == "text":
            content.text += proxy_event["delta"]
            return {
                "type": "text_delta",
                "content_index": content_index,
                "delta": proxy_event["delta"],
                "partial": partial,
            }
        raise ValueError("Received text_delta for non-text content")

    elif event_type == "text_end":
        content_index = proxy_event["content_index"]
        content = partial.content[content_index]
        if content.type == "text":
            content.text_signature = proxy_event.get("content_signature")
            return {
                "type": "text_end",
                "content_index": content_index,
                "content": content.text,
                "partial": partial,
            }
        raise ValueError("Received text_end for non-text content")

    elif event_type == "thinking_start":
        content_index = proxy_event["content_index"]
        partial.content.insert(content_index, ThinkingContent(type="thinking", thinking=""))
        return {"type": "thinking_start", "content_index": content_index, "partial": partial}

    elif event_type == "thinking_delta":
        content_index = proxy_event["content_index"]
        content = partial.content[content_index]
        if content.type == "thinking":
            content.thinking += proxy_event["delta"]
            return {
                "type": "thinking_delta",
                "content_index": content_index,
                "delta": proxy_event["delta"],
                "partial": partial,
            }
        raise ValueError("Received thinking_delta for non-thinking content")

    elif event_type == "thinking_end":
        content_index = proxy_event["content_index"]
        content = partial.content[content_index]
        if content.type == "thinking":
            content.thinking_signature = proxy_event.get("content_signature")
            return {
                "type": "thinking_end",
                "content_index": content_index,
                "content": content.thinking,
                "partial": partial,
            }
        raise ValueError("Received thinking_end for non-thinking content")

    elif event_type == "toolcall_start":
        content_index = proxy_event["content_index"]
        tool_call = ToolCall(
            type="toolCall",
            id=proxy_event["id"],
            name=proxy_event["tool_name"],
            arguments={},
        )
        tool_call._partial_json = ""  # type: ignore
        partial.content.insert(content_index, tool_call)
        return {"type": "toolcall_start", "content_index": content_index, "partial": partial}

    elif event_type == "toolcall_delta":
        content_index = proxy_event["content_index"]
        content = partial.content[content_index]
        if content.type == "toolCall":
            content._partial_json += proxy_event["delta"]  # type: ignore
            content.arguments = parse_streaming_json(content._partial_json) or {}  # type: ignore
            return {
                "type": "toolcall_delta",
                "content_index": content_index,
                "delta": proxy_event["delta"],
                "partial": partial,
            }
        raise ValueError("Received toolcall_delta for non-toolCall content")

    elif event_type == "toolcall_end":
        content_index = proxy_event["content_index"]
        content = partial.content[content_index]
        if content.type == "toolCall":
            if hasattr(content, "_partial_json"):
                delattr(content, "_partial_json")
            return {
                "type": "toolcall_end",
                "content_index": content_index,
                "tool_call": content,
                "partial": partial,
            }
        return None

    elif event_type == "done":
        partial.stop_reason = proxy_event["reason"]
        partial.usage = Usage.model_validate(proxy_event["usage"])
        return {"type": "done", "reason": proxy_event["reason"], "message": partial}

    elif event_type == "error":
        partial.stop_reason = proxy_event["reason"]
        partial.error_message = proxy_event.get("error_message")
        partial.usage = Usage.model_validate(proxy_event["usage"])
        return {"type": "error", "reason": proxy_event["reason"], "error": partial}

    else:
        print(f"Unhandled proxy event type: {event_type}")
        return None
