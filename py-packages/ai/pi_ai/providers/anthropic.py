"""
Anthropic Messages API provider implementation.
"""

from __future__ import annotations

import asyncio
import time
from typing import Any

from pydantic import BaseModel

from pi_ai.env_api_keys import get_env_api_key
from pi_ai.event_stream import AssistantMessageEventStream
from pi_ai.models import calculate_cost
from pi_ai.types import (
    AssistantMessage,
    CacheRetention,
    Context,
    ImageContent,
    Message,
    Model,
    SimpleStreamOptions,
    StopReason,
    StreamOptions,
    TextContent,
    ThinkingContent,
    Tool,
    ToolCall,
    ToolResultMessage,
    Usage,
    UsageCost,
)
from pi_ai.providers.simple_options import adjust_max_tokens_for_thinking, build_base_options
from pi_ai.providers.transform_messages import transform_messages
from pi_ai.utils.json_parse import parse_streaming_json

try:
    import anthropic
    from anthropic import Anthropic
    from anthropic.types import MessageParam, ContentBlockParam

    _HAS_ANTHROPIC = True
except ImportError:
    _HAS_ANTHROPIC = False


class AnthropicOptions(StreamOptions):
    """Options specific to Anthropic API."""

    thinking_enabled: bool | None = None
    thinking_budget_tokens: int | None = None
    interleaved_thinking: bool | None = None
    tool_choice: str | dict[str, Any] | None = None


def _resolve_cache_retention(cache_retention: CacheRetention | None) -> CacheRetention:
    """Resolve cache retention preference."""
    import os

    if cache_retention:
        return cache_retention
    if os.environ.get("PI_CACHE_RETENTION") == "long":
        return "long"
    return "short"


def _get_cache_control(
    base_url: str,
    cache_retention: CacheRetention | None = None,
) -> tuple[CacheRetention, dict[str, Any] | None]:
    """Get cache control settings."""
    retention = _resolve_cache_retention(cache_retention)
    if retention == "none":
        return retention, None

    ttl = "1h" if retention == "long" and "api.anthropic.com" in base_url else None
    cache_control: dict[str, Any] = {"type": "ephemeral"}
    if ttl:
        cache_control["ttl"] = ttl

    return retention, cache_control


def _sanitize_surrogates(text: str) -> str:
    """Remove surrogate characters from text."""
    return text.encode("utf-8", errors="replace").decode("utf-8")


def _normalize_tool_call_id(id: str) -> str:
    """Normalize tool call ID for Anthropic API."""
    import re

    normalized = re.sub(r"[^a-zA-Z0-9_-]", "_", id)
    return normalized[:64]


def _convert_content_blocks(
    content: list[TextContent | ImageContent],
) -> str | list[dict[str, Any]]:
    """Convert content blocks to Anthropic API format."""
    has_images = any(c.type == "image" for c in content)

    if not has_images:
        return _sanitize_surrogates(
            "\n".join(c.text for c in content if c.type == "text")
        )

    blocks: list[dict[str, Any]] = []
    for block in content:
        if block.type == "text":
            blocks.append({"type": "text", "text": _sanitize_surrogates(block.text)})
        elif block.type == "image":
            blocks.append({
                "type": "image",
                "source": {
                    "type": "base64",
                    "media_type": block.mime_type,
                    "data": block.data,
                },
            })

    # If only images, add placeholder text
    if not any(b["type"] == "text" for b in blocks):
        blocks.insert(0, {"type": "text", "text": "(see attached image)"})

    return blocks


def _map_stop_reason(reason: str) -> StopReason:
    """Map Anthropic stop reason to standard stop reason."""
    mapping: dict[str, StopReason] = {
        "end_turn": "stop",
        "max_tokens": "length",
        "tool_use": "toolUse",
        "refusal": "error",
        "pause_turn": "stop",
        "stop_sequence": "stop",
        "sensitive": "error",
    }
    return mapping.get(reason, "error")


def stream_anthropic(
    model: Model,
    context: Context,
    options: AnthropicOptions | None = None,
) -> AssistantMessageEventStream:
    """Stream an assistant message using Anthropic API."""
    if not _HAS_ANTHROPIC:
        raise ImportError("anthropic package is required for Anthropic API")

    stream = AssistantMessageEventStream()
    options = options or AnthropicOptions()

    async def _run() -> None:
        output = AssistantMessage(
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
            api_key = options.api_key or get_env_api_key(model.provider) or ""
            is_oauth = "sk-ant-oat" in api_key

            # Create client
            client_kwargs: dict[str, Any] = {
                "base_url": model.base_url,
            }

            if is_oauth:
                client_kwargs["api_key"] = None
                client_kwargs["auth_token"] = api_key
            else:
                client_kwargs["api_key"] = api_key

            headers = {
                "accept": "application/json",
                "anthropic-dangerous-direct-browser-access": "true",
            }

            beta_features = ["fine-grained-tool-streaming-2025-05-14"]
            interleaved = options.interleaved_thinking if options.interleaved_thinking is not None else True
            if interleaved:
                beta_features.append("interleaved-thinking-2025-05-14")

            if is_oauth:
                headers["anthropic-beta"] = f"claude-code-20250219,oauth-2025-04-20,{','.join(beta_features)}"
                headers["user-agent"] = "claude-cli/2.1.2 (external, cli)"
                headers["x-app"] = "cli"
            else:
                headers["anthropic-beta"] = ",".join(beta_features)

            if model.headers:
                headers.update(model.headers)
            if options.headers:
                headers.update(options.headers)

            client_kwargs["default_headers"] = headers
            client = Anthropic(**client_kwargs)

            # Build params
            _, cache_control = _get_cache_control(model.base_url, options.cache_retention)
            transformed = transform_messages(
                context.messages, model, lambda id, m, s: _normalize_tool_call_id(id)
            )

            messages_params: list[dict[str, Any]] = []
            i = 0
            while i < len(transformed):
                msg = transformed[i]

                if msg.role == "user":
                    if isinstance(msg.content, str):
                        if msg.content.strip():
                            messages_params.append({
                                "role": "user",
                                "content": _sanitize_surrogates(msg.content),
                            })
                    else:
                        blocks = []
                        for item in msg.content:
                            if item.type == "text":
                                blocks.append({
                                    "type": "text",
                                    "text": _sanitize_surrogates(item.text),
                                })
                            elif item.type == "image" and "image" in model.input:
                                blocks.append({
                                    "type": "image",
                                    "source": {
                                        "type": "base64",
                                        "media_type": item.mime_type,
                                        "data": item.data,
                                    },
                                })
                        if blocks:
                            messages_params.append({"role": "user", "content": blocks})

                elif msg.role == "assistant":
                    blocks = []
                    for block in msg.content:
                        if block.type == "text" and block.text.strip():
                            blocks.append({
                                "type": "text",
                                "text": _sanitize_surrogates(block.text),
                            })
                        elif block.type == "thinking" and block.thinking.strip():
                            if block.thinking_signature:
                                blocks.append({
                                    "type": "thinking",
                                    "thinking": _sanitize_surrogates(block.thinking),
                                    "signature": block.thinking_signature,
                                })
                            else:
                                blocks.append({
                                    "type": "text",
                                    "text": _sanitize_surrogates(block.thinking),
                                })
                        elif block.type == "toolCall":
                            blocks.append({
                                "type": "tool_use",
                                "id": block.id,
                                "name": block.name,
                                "input": block.arguments or {},
                            })
                    if blocks:
                        messages_params.append({"role": "assistant", "content": blocks})

                elif msg.role == "toolResult":
                    tool_results = []
                    j = i
                    while j < len(transformed) and transformed[j].role == "toolResult":
                        tr = transformed[j]
                        tool_results.append({
                            "type": "tool_result",
                            "tool_use_id": tr.tool_call_id,
                            "content": _convert_content_blocks(tr.content),
                            "is_error": tr.is_error,
                        })
                        j += 1
                    i = j - 1
                    messages_params.append({"role": "user", "content": tool_results})

                i += 1

            # Add cache control to last user message
            if cache_control and messages_params:
                last_msg = messages_params[-1]
                if last_msg.get("role") == "user":
                    content = last_msg.get("content")
                    if isinstance(content, list) and content:
                        last_block = content[-1]
                        if last_block.get("type") in ("text", "image", "tool_result"):
                            last_block["cache_control"] = cache_control
                    elif isinstance(content, str):
                        last_msg["content"] = [{
                            "type": "text",
                            "text": content,
                            "cache_control": cache_control,
                        }]

            params: dict[str, Any] = {
                "model": model.id,
                "messages": messages_params,
                "max_tokens": options.max_tokens or (model.max_tokens // 3),
                "stream": True,
            }

            # System prompt
            system_content = []
            if is_oauth:
                system_content.append({
                    "type": "text",
                    "text": "You are Claude Code, Anthropic's official CLI for Claude.",
                    **({"cache_control": cache_control} if cache_control else {}),
                })
            if context.system_prompt:
                system_content.append({
                    "type": "text",
                    "text": _sanitize_surrogates(context.system_prompt),
                    **({"cache_control": cache_control} if cache_control else {}),
                })
            if system_content:
                params["system"] = system_content

            if options.temperature is not None:
                params["temperature"] = options.temperature

            if context.tools:
                params["tools"] = [
                    {
                        "name": tool.name,
                        "description": tool.description,
                        "input_schema": {
                            "type": "object",
                            "properties": tool.parameters.get("properties", {}),
                            "required": tool.parameters.get("required", []),
                        },
                    }
                    for tool in context.tools
                ]

            if options.thinking_enabled and model.reasoning:
                params["thinking"] = {
                    "type": "enabled",
                    "budget_tokens": options.thinking_budget_tokens or 1024,
                }

            if options.tool_choice:
                if isinstance(options.tool_choice, str):
                    params["tool_choice"] = {"type": options.tool_choice}
                else:
                    params["tool_choice"] = options.tool_choice

            # Stream the response
            stream.push({"type": "start", "partial": output})

            with client.messages.stream(**params) as response:
                block_map: dict[int, dict[str, Any]] = {}

                for event in response:
                    if event.type == "message_start":
                        usage = event.message.usage
                        output.usage.input = usage.input_tokens or 0
                        output.usage.output = usage.output_tokens or 0
                        output.usage.cache_read = getattr(usage, "cache_read_input_tokens", 0) or 0
                        output.usage.cache_write = getattr(usage, "cache_creation_input_tokens", 0) or 0
                        output.usage.total_tokens = (
                            output.usage.input + output.usage.output +
                            output.usage.cache_read + output.usage.cache_write
                        )
                        calculate_cost(model, output.usage)

                    elif event.type == "content_block_start":
                        idx = event.index
                        if event.content_block.type == "text":
                            block = TextContent(type="text", text="")
                            output.content.append(block)
                            block_map[idx] = {"type": "text", "index": len(output.content) - 1}
                            stream.push({
                                "type": "text_start",
                                "content_index": len(output.content) - 1,
                                "partial": output,
                            })
                        elif event.content_block.type == "thinking":
                            block = ThinkingContent(type="thinking", thinking="")
                            output.content.append(block)
                            block_map[idx] = {"type": "thinking", "index": len(output.content) - 1}
                            stream.push({
                                "type": "thinking_start",
                                "content_index": len(output.content) - 1,
                                "partial": output,
                            })
                        elif event.content_block.type == "tool_use":
                            block = ToolCall(
                                type="toolCall",
                                id=event.content_block.id,
                                name=event.content_block.name,
                                arguments={},
                            )
                            output.content.append(block)
                            block_map[idx] = {
                                "type": "toolCall",
                                "index": len(output.content) - 1,
                                "partial_json": "",
                            }
                            stream.push({
                                "type": "toolcall_start",
                                "content_index": len(output.content) - 1,
                                "partial": output,
                            })

                    elif event.type == "content_block_delta":
                        idx = event.index
                        info = block_map.get(idx)
                        if not info:
                            continue

                        content_idx = info["index"]
                        block = output.content[content_idx]

                        if event.delta.type == "text_delta" and block.type == "text":
                            block.text += event.delta.text
                            stream.push({
                                "type": "text_delta",
                                "content_index": content_idx,
                                "delta": event.delta.text,
                                "partial": output,
                            })
                        elif event.delta.type == "thinking_delta" and block.type == "thinking":
                            block.thinking += event.delta.thinking
                            stream.push({
                                "type": "thinking_delta",
                                "content_index": content_idx,
                                "delta": event.delta.thinking,
                                "partial": output,
                            })
                        elif event.delta.type == "input_json_delta" and block.type == "toolCall":
                            info["partial_json"] += event.delta.partial_json
                            block.arguments = parse_streaming_json(info["partial_json"])
                            stream.push({
                                "type": "toolcall_delta",
                                "content_index": content_idx,
                                "delta": event.delta.partial_json,
                                "partial": output,
                            })
                        elif hasattr(event.delta, "signature") and block.type == "thinking":
                            block.thinking_signature = (block.thinking_signature or "") + event.delta.signature

                    elif event.type == "content_block_stop":
                        idx = event.index
                        info = block_map.get(idx)
                        if not info:
                            continue

                        content_idx = info["index"]
                        block = output.content[content_idx]

                        if block.type == "text":
                            stream.push({
                                "type": "text_end",
                                "content_index": content_idx,
                                "content": block.text,
                                "partial": output,
                            })
                        elif block.type == "thinking":
                            stream.push({
                                "type": "thinking_end",
                                "content_index": content_idx,
                                "content": block.thinking,
                                "partial": output,
                            })
                        elif block.type == "toolCall":
                            block.arguments = parse_streaming_json(info.get("partial_json", ""))
                            stream.push({
                                "type": "toolcall_end",
                                "content_index": content_idx,
                                "tool_call": block,
                                "partial": output,
                            })

                    elif event.type == "message_delta":
                        if hasattr(event.delta, "stop_reason") and event.delta.stop_reason:
                            output.stop_reason = _map_stop_reason(event.delta.stop_reason)
                        if hasattr(event, "usage"):
                            if getattr(event.usage, "input_tokens", None) is not None:
                                output.usage.input = event.usage.input_tokens
                            if getattr(event.usage, "output_tokens", None) is not None:
                                output.usage.output = event.usage.output_tokens
                            if getattr(event.usage, "cache_read_input_tokens", None) is not None:
                                output.usage.cache_read = event.usage.cache_read_input_tokens
                            if getattr(event.usage, "cache_creation_input_tokens", None) is not None:
                                output.usage.cache_write = event.usage.cache_creation_input_tokens
                            output.usage.total_tokens = (
                                output.usage.input + output.usage.output +
                                output.usage.cache_read + output.usage.cache_write
                            )
                            calculate_cost(model, output.usage)

            stream.push({"type": "done", "reason": output.stop_reason, "message": output})
            stream.end()

        except Exception as e:
            output.stop_reason = "error"
            output.error_message = str(e)
            stream.push({"type": "error", "reason": "error", "error": output})
            stream.end()

    # Run async
    asyncio.get_event_loop().create_task(_run())
    return stream


def stream_simple_anthropic(
    model: Model,
    context: Context,
    options: SimpleStreamOptions | None = None,
) -> AssistantMessageEventStream:
    """Stream an assistant message using simplified options."""
    api_key = (options.api_key if options else None) or get_env_api_key(model.provider)
    if not api_key:
        raise ValueError(f"No API key for provider: {model.provider}")

    base = build_base_options(model, options, api_key)

    if not options or not options.reasoning:
        return stream_anthropic(
            model, context,
            AnthropicOptions(
                **base.model_dump(),
                thinking_enabled=False,
            )
        )

    max_tokens, thinking_budget = adjust_max_tokens_for_thinking(
        base.max_tokens or 0,
        model.max_tokens,
        options.reasoning,
        options.thinking_budgets,
    )

    return stream_anthropic(
        model, context,
        AnthropicOptions(
            **base.model_dump(),
            max_tokens=max_tokens,
            thinking_enabled=True,
            thinking_budget_tokens=thinking_budget,
        )
    )
