"""
OpenAI Completions API provider implementation.
"""

from __future__ import annotations

import asyncio
import json
import time
from typing import Any

from pydantic import BaseModel

from pi_ai.env_api_keys import get_env_api_key
from pi_ai.event_stream import AssistantMessageEventStream
from pi_ai.models import calculate_cost, supports_xhigh
from pi_ai.types import (
    AssistantMessage,
    Context,
    Message,
    Model,
    OpenAICompletionsCompat,
    SimpleStreamOptions,
    StopReason,
    StreamOptions,
    TextContent,
    ThinkingContent,
    Tool,
    ToolCall,
    ToolResultMessage,
    Usage,
)
from pi_ai.providers.simple_options import build_base_options, clamp_reasoning
from pi_ai.providers.transform_messages import transform_messages
from pi_ai.utils.json_parse import parse_streaming_json

try:
    from openai import OpenAI

    _HAS_OPENAI = True
except ImportError:
    _HAS_OPENAI = False


class OpenAICompletionsOptions(StreamOptions):
    """Options specific to OpenAI Completions API."""

    tool_choice: str | dict[str, Any] | None = None
    reasoning_effort: str | None = None


def _sanitize_surrogates(text: str) -> str:
    """Remove surrogate characters from text."""
    return text.encode("utf-8", errors="replace").decode("utf-8")


def _normalize_mistral_tool_id(id: str) -> str:
    """Normalize tool call ID for Mistral (exactly 9 alphanumeric chars)."""
    import re

    normalized = re.sub(r"[^a-zA-Z0-9]", "", id)
    if len(normalized) < 9:
        padding = "ABCDEFGHI"
        normalized = normalized + padding[: 9 - len(normalized)]
    elif len(normalized) > 9:
        normalized = normalized[:9]
    return normalized


def _has_tool_history(messages: list[Message]) -> bool:
    """Check if conversation has tool calls or tool results."""
    for msg in messages:
        if msg.role == "toolResult":
            return True
        if msg.role == "assistant":
            if any(b.type == "toolCall" for b in msg.content):
                return True
    return False


def _map_stop_reason(reason: str | None) -> StopReason:
    """Map OpenAI stop reason to standard stop reason."""
    if reason is None:
        return "stop"
    mapping: dict[str, StopReason] = {
        "stop": "stop",
        "length": "length",
        "function_call": "toolUse",
        "tool_calls": "toolUse",
        "content_filter": "error",
    }
    return mapping.get(reason, "error")


def _detect_compat(model: Model) -> dict[str, Any]:
    """Detect compatibility settings from provider and base URL."""
    provider = model.provider
    base_url = model.base_url

    is_zai = provider == "zai" or "api.z.ai" in base_url

    is_non_standard = any([
        provider == "cerebras" or "cerebras.ai" in base_url,
        provider == "xai" or "api.x.ai" in base_url,
        provider == "mistral" or "mistral.ai" in base_url,
        "chutes.ai" in base_url,
        "deepseek.com" in base_url,
        is_zai,
        provider == "opencode" or "opencode.ai" in base_url,
    ])

    use_max_tokens = any([
        provider == "mistral" or "mistral.ai" in base_url,
        "chutes.ai" in base_url,
    ])

    is_grok = provider == "xai" or "api.x.ai" in base_url
    is_mistral = provider == "mistral" or "mistral.ai" in base_url

    return {
        "supports_store": not is_non_standard,
        "supports_developer_role": not is_non_standard,
        "supports_reasoning_effort": not is_grok and not is_zai,
        "supports_usage_in_streaming": True,
        "max_tokens_field": "max_tokens" if use_max_tokens else "max_completion_tokens",
        "requires_tool_result_name": is_mistral,
        "requires_assistant_after_tool_result": False,
        "requires_thinking_as_text": is_mistral,
        "requires_mistral_tool_ids": is_mistral,
        "thinking_format": "zai" if is_zai else "openai",
        "open_router_routing": {},
        "vercel_gateway_routing": {},
        "supports_strict_mode": True,
    }


def _get_compat(model: Model) -> dict[str, Any]:
    """Get resolved compatibility settings for a model."""
    detected = _detect_compat(model)
    if not model.compat:
        return detected

    compat = model.compat
    if isinstance(compat, OpenAICompletionsCompat):
        result = detected.copy()
        if compat.supports_store is not None:
            result["supports_store"] = compat.supports_store
        if compat.supports_developer_role is not None:
            result["supports_developer_role"] = compat.supports_developer_role
        if compat.supports_reasoning_effort is not None:
            result["supports_reasoning_effort"] = compat.supports_reasoning_effort
        if compat.supports_usage_in_streaming is not None:
            result["supports_usage_in_streaming"] = compat.supports_usage_in_streaming
        if compat.max_tokens_field is not None:
            result["max_tokens_field"] = compat.max_tokens_field
        if compat.requires_tool_result_name is not None:
            result["requires_tool_result_name"] = compat.requires_tool_result_name
        if compat.requires_assistant_after_tool_result is not None:
            result["requires_assistant_after_tool_result"] = compat.requires_assistant_after_tool_result
        if compat.requires_thinking_as_text is not None:
            result["requires_thinking_as_text"] = compat.requires_thinking_as_text
        if compat.requires_mistral_tool_ids is not None:
            result["requires_mistral_tool_ids"] = compat.requires_mistral_tool_ids
        if compat.thinking_format is not None:
            result["thinking_format"] = compat.thinking_format
        if compat.open_router_routing is not None:
            result["open_router_routing"] = compat.open_router_routing.model_dump()
        if compat.vercel_gateway_routing is not None:
            result["vercel_gateway_routing"] = compat.vercel_gateway_routing.model_dump()
        if compat.supports_strict_mode is not None:
            result["supports_strict_mode"] = compat.supports_strict_mode
        return result

    return detected


def stream_openai_completions(
    model: Model,
    context: Context,
    options: OpenAICompletionsOptions | None = None,
) -> AssistantMessageEventStream:
    """Stream an assistant message using OpenAI Completions API."""
    if not _HAS_OPENAI:
        raise ImportError("openai package is required for OpenAI API")

    stream = AssistantMessageEventStream()
    options = options or OpenAICompletionsOptions()

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

            # Create client
            headers = dict(model.headers) if model.headers else {}

            if model.provider == "github-copilot":
                messages = context.messages or []
                last_message = messages[-1] if messages else None
                is_agent_call = last_message and last_message.role != "user"
                headers["X-Initiator"] = "agent" if is_agent_call else "user"
                headers["Openai-Intent"] = "conversation-edits"

                # Check for images
                has_images = any(
                    (msg.role == "user" and isinstance(msg.content, list) and
                     any(c.type == "image" for c in msg.content)) or
                    (msg.role == "toolResult" and any(c.type == "image" for c in msg.content))
                    for msg in messages
                )
                if has_images:
                    headers["Copilot-Vision-Request"] = "true"

            if options.headers:
                headers.update(options.headers)

            client = OpenAI(
                api_key=api_key,
                base_url=model.base_url,
                default_headers=headers if headers else None,
            )

            compat = _get_compat(model)

            # Normalize tool call ID
            def normalize_tool_call_id(id: str, m: Model, s: AssistantMessage) -> str:
                if compat["requires_mistral_tool_ids"]:
                    return _normalize_mistral_tool_id(id)
                if "|" in id:
                    import re

                    call_id = id.split("|")[0]
                    return re.sub(r"[^a-zA-Z0-9_-]", "_", call_id)[:40]
                if model.provider == "openai":
                    return id[:40] if len(id) > 40 else id
                if model.provider == "github-copilot" and "claude" in model.id.lower():
                    import re

                    return re.sub(r"[^a-zA-Z0-9_-]", "_", id)[:64]
                return id

            transformed = transform_messages(context.messages, model, normalize_tool_call_id)

            # Build messages
            messages_params: list[dict[str, Any]] = []

            if context.system_prompt:
                use_developer = model.reasoning and compat["supports_developer_role"]
                role = "developer" if use_developer else "system"
                messages_params.append({
                    "role": role,
                    "content": _sanitize_surrogates(context.system_prompt),
                })

            last_role: str | None = None

            for i, msg in enumerate(transformed):
                # Insert synthetic assistant message if needed
                if (compat["requires_assistant_after_tool_result"] and
                        last_role == "toolResult" and msg.role == "user"):
                    messages_params.append({
                        "role": "assistant",
                        "content": "I have processed the tool results.",
                    })

                if msg.role == "user":
                    if isinstance(msg.content, str):
                        messages_params.append({
                            "role": "user",
                            "content": _sanitize_surrogates(msg.content),
                        })
                    else:
                        content = []
                        for item in msg.content:
                            if item.type == "text":
                                content.append({
                                    "type": "text",
                                    "text": _sanitize_surrogates(item.text),
                                })
                            elif item.type == "image" and "image" in model.input:
                                content.append({
                                    "type": "image_url",
                                    "image_url": {
                                        "url": f"data:{item.mime_type};base64,{item.data}",
                                    },
                                })
                        if content:
                            messages_params.append({"role": "user", "content": content})

                elif msg.role == "assistant":
                    assistant_msg: dict[str, Any] = {
                        "role": "assistant",
                        "content": "" if compat["requires_assistant_after_tool_result"] else None,
                    }

                    # Text content
                    text_blocks = [b for b in msg.content if b.type == "text" and b.text.strip()]
                    if text_blocks:
                        if model.provider == "github-copilot":
                            assistant_msg["content"] = "".join(
                                _sanitize_surrogates(b.text) for b in text_blocks
                            )
                        else:
                            assistant_msg["content"] = [
                                {"type": "text", "text": _sanitize_surrogates(b.text)}
                                for b in text_blocks
                            ]

                    # Thinking content
                    thinking_blocks = [
                        b for b in msg.content
                        if b.type == "thinking" and b.thinking.strip()
                    ]
                    if thinking_blocks:
                        if compat["requires_thinking_as_text"]:
                            thinking_text = "\n\n".join(b.thinking for b in thinking_blocks)
                            if isinstance(assistant_msg["content"], list):
                                assistant_msg["content"].insert(0, {
                                    "type": "text",
                                    "text": thinking_text,
                                })
                            else:
                                assistant_msg["content"] = [{"type": "text", "text": thinking_text}]
                        else:
                            sig = thinking_blocks[0].thinking_signature
                            if sig:
                                assistant_msg[sig] = "\n".join(b.thinking for b in thinking_blocks)

                    # Tool calls
                    tool_calls = [b for b in msg.content if b.type == "toolCall"]
                    if tool_calls:
                        assistant_msg["tool_calls"] = [
                            {
                                "id": tc.id,
                                "type": "function",
                                "function": {
                                    "name": tc.name,
                                    "arguments": json.dumps(tc.arguments),
                                },
                            }
                            for tc in tool_calls
                        ]

                    # Skip empty assistant messages
                    content = assistant_msg["content"]
                    has_content = content is not None and (
                        isinstance(content, str) and len(content) > 0 or
                        isinstance(content, list) and len(content) > 0
                    )
                    if has_content or assistant_msg.get("tool_calls"):
                        messages_params.append(assistant_msg)

                elif msg.role == "toolResult":
                    image_blocks: list[dict[str, Any]] = []
                    j = i
                    while j < len(transformed) and transformed[j].role == "toolResult":
                        tr = transformed[j]
                        text_result = "\n".join(
                            c.text for c in tr.content if c.type == "text"
                        )
                        has_text = len(text_result) > 0

                        tool_result: dict[str, Any] = {
                            "role": "tool",
                            "content": _sanitize_surrogates(
                                text_result if has_text else "(see attached image)"
                            ),
                            "tool_call_id": tr.tool_call_id,
                        }
                        if compat["requires_tool_result_name"] and tr.tool_name:
                            tool_result["name"] = tr.tool_name
                        messages_params.append(tool_result)

                        # Collect images
                        if "image" in model.input:
                            for c in tr.content:
                                if c.type == "image":
                                    image_blocks.append({
                                        "type": "image_url",
                                        "image_url": {
                                            "url": f"data:{c.mime_type};base64,{c.data}",
                                        },
                                    })
                        j += 1

                    # Add images as user message
                    if image_blocks:
                        if compat["requires_assistant_after_tool_result"]:
                            messages_params.append({
                                "role": "assistant",
                                "content": "I have processed the tool results.",
                            })
                        messages_params.append({
                            "role": "user",
                            "content": [
                                {"type": "text", "text": "Attached image(s) from tool result:"},
                                *image_blocks,
                            ],
                        })
                        last_role = "user"
                        continue

                    last_role = "toolResult"
                    continue

                last_role = msg.role

            # Build request params
            params: dict[str, Any] = {
                "model": model.id,
                "messages": messages_params,
                "stream": True,
            }

            if compat["supports_usage_in_streaming"]:
                params["stream_options"] = {"include_usage": True}

            if compat["supports_store"]:
                params["store"] = False

            if options.max_tokens:
                if compat["max_tokens_field"] == "max_tokens":
                    params["max_tokens"] = options.max_tokens
                else:
                    params["max_completion_tokens"] = options.max_tokens

            if options.temperature is not None:
                params["temperature"] = options.temperature

            if context.tools:
                params["tools"] = [
                    {
                        "type": "function",
                        "function": {
                            "name": tool.name,
                            "description": tool.description,
                            "parameters": tool.parameters,
                            **({"strict": False} if compat["supports_strict_mode"] else {}),
                        },
                    }
                    for tool in context.tools
                ]
            elif _has_tool_history(context.messages):
                params["tools"] = []

            if options.tool_choice:
                params["tool_choice"] = options.tool_choice

            # Thinking/reasoning
            if compat["thinking_format"] == "zai" and model.reasoning:
                params["thinking"] = {
                    "type": "enabled" if options.reasoning_effort else "disabled"
                }
            elif compat["thinking_format"] == "qwen" and model.reasoning:
                params["enable_thinking"] = bool(options.reasoning_effort)
            elif options.reasoning_effort and model.reasoning and compat["supports_reasoning_effort"]:
                params["reasoning_effort"] = options.reasoning_effort

            # Provider routing
            if "openrouter.ai" in model.base_url and model.compat:
                if isinstance(model.compat, OpenAICompletionsCompat) and model.compat.open_router_routing:
                    params["provider"] = model.compat.open_router_routing.model_dump()

            # Stream the response
            stream.push({"type": "start", "partial": output})

            current_block: TextContent | ThinkingContent | ToolCall | None = None

            def block_index() -> int:
                return len(output.content) - 1

            def finish_current_block(block: TextContent | ThinkingContent | ToolCall | None) -> None:
                if not block:
                    return
                if block.type == "text":
                    stream.push({
                        "type": "text_end",
                        "content_index": block_index(),
                        "content": block.text,
                        "partial": output,
                    })
                elif block.type == "thinking":
                    stream.push({
                        "type": "thinking_end",
                        "content_index": block_index(),
                        "content": block.thinking,
                        "partial": output,
                    })
                elif block.type == "toolCall":
                    if hasattr(block, "_partial_args"):
                        block.arguments = json.loads(block._partial_args or "{}")
                        delattr(block, "_partial_args")
                    stream.push({
                        "type": "toolcall_end",
                        "content_index": block_index(),
                        "tool_call": block,
                        "partial": output,
                    })

            response = client.chat.completions.create(**params)

            for chunk in response:
                if chunk.usage:
                    cached = getattr(chunk.usage, "prompt_tokens_details", None)
                    cached_tokens = cached.cached_tokens if cached else 0
                    reasoning = getattr(chunk.usage, "completion_tokens_details", None)
                    reasoning_tokens = reasoning.reasoning_tokens if reasoning else 0

                    input_tokens = (chunk.usage.prompt_tokens or 0) - cached_tokens
                    output_tokens = (chunk.usage.completion_tokens or 0) + reasoning_tokens

                    output.usage.input = input_tokens
                    output.usage.output = output_tokens
                    output.usage.cache_read = cached_tokens
                    output.usage.cache_write = 0
                    output.usage.total_tokens = input_tokens + output_tokens + cached_tokens
                    calculate_cost(model, output.usage)

                if not chunk.choices:
                    continue

                choice = chunk.choices[0]

                if choice.finish_reason:
                    output.stop_reason = _map_stop_reason(choice.finish_reason)

                if choice.delta:
                    delta = choice.delta

                    # Text content
                    if delta.content:
                        if not current_block or current_block.type != "text":
                            finish_current_block(current_block)
                            current_block = TextContent(type="text", text="")
                            output.content.append(current_block)
                            stream.push({
                                "type": "text_start",
                                "content_index": block_index(),
                                "partial": output,
                            })
                        current_block.text += delta.content
                        stream.push({
                            "type": "text_delta",
                            "content_index": block_index(),
                            "delta": delta.content,
                            "partial": output,
                        })

                    # Reasoning content
                    reasoning_fields = ["reasoning_content", "reasoning", "reasoning_text"]
                    for field in reasoning_fields:
                        reasoning_content = getattr(delta, field, None)
                        if reasoning_content:
                            if not current_block or current_block.type != "thinking":
                                finish_current_block(current_block)
                                current_block = ThinkingContent(
                                    type="thinking",
                                    thinking="",
                                    thinking_signature=field,
                                )
                                output.content.append(current_block)
                                stream.push({
                                    "type": "thinking_start",
                                    "content_index": block_index(),
                                    "partial": output,
                                })
                            current_block.thinking += reasoning_content
                            stream.push({
                                "type": "thinking_delta",
                                "content_index": block_index(),
                                "delta": reasoning_content,
                                "partial": output,
                            })
                            break

                    # Tool calls
                    if delta.tool_calls:
                        for tc in delta.tool_calls:
                            if (not current_block or current_block.type != "toolCall" or
                                    (tc.id and current_block.id != tc.id)):
                                finish_current_block(current_block)
                                current_block = ToolCall(
                                    type="toolCall",
                                    id=tc.id or "",
                                    name=tc.function.name if tc.function else "",
                                    arguments={},
                                )
                                current_block._partial_args = ""  # type: ignore
                                output.content.append(current_block)
                                stream.push({
                                    "type": "toolcall_start",
                                    "content_index": block_index(),
                                    "partial": output,
                                })

                            if tc.id:
                                current_block.id = tc.id
                            if tc.function and tc.function.name:
                                current_block.name = tc.function.name

                            delta_args = ""
                            if tc.function and tc.function.arguments:
                                delta_args = tc.function.arguments
                                current_block._partial_args += delta_args  # type: ignore
                                current_block.arguments = parse_streaming_json(
                                    current_block._partial_args  # type: ignore
                                )

                            stream.push({
                                "type": "toolcall_delta",
                                "content_index": block_index(),
                                "delta": delta_args,
                                "partial": output,
                            })

            finish_current_block(current_block)
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


def stream_simple_openai_completions(
    model: Model,
    context: Context,
    options: SimpleStreamOptions | None = None,
) -> AssistantMessageEventStream:
    """Stream an assistant message using simplified options."""
    api_key = (options.api_key if options else None) or get_env_api_key(model.provider)
    if not api_key:
        raise ValueError(f"No API key for provider: {model.provider}")

    base = build_base_options(model, options, api_key)
    reasoning_effort = (
        options.reasoning if options and supports_xhigh(model) else
        clamp_reasoning(options.reasoning if options else None)
    )

    return stream_openai_completions(
        model, context,
        OpenAICompletionsOptions(
            **base.model_dump(),
            reasoning_effort=reasoning_effort,
        )
    )
