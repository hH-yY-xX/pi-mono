"""
Message transformation utilities for cross-provider compatibility.
"""

from __future__ import annotations

import time
from typing import Callable

from pi_ai.types import (
    Api,
    AssistantMessage,
    Message,
    Model,
    TextContent,
    ToolCall,
    ToolResultMessage,
)


def transform_messages(
    messages: list[Message],
    model: Model,
    normalize_tool_call_id: Callable[[str, Model, AssistantMessage], str] | None = None,
) -> list[Message]:
    """
    Transform messages for cross-provider compatibility.
    
    Handles:
    - Thinking block conversion for different models
    - Tool call ID normalization
    - Synthetic tool results for orphaned tool calls
    - Filtering errored/aborted assistant messages
    
    Args:
        messages: List of messages to transform
        model: Target model
        normalize_tool_call_id: Optional function to normalize tool call IDs
    
    Returns:
        Transformed list of messages
    """
    # Build a map of original tool call IDs to normalized IDs
    tool_call_id_map: dict[str, str] = {}

    # First pass: transform messages
    transformed: list[Message] = []
    for msg in messages:
        # User messages pass through unchanged
        if msg.role == "user":
            transformed.append(msg)
            continue

        # Handle toolResult messages - normalize toolCallId if we have a mapping
        if msg.role == "toolResult":
            normalized_id = tool_call_id_map.get(msg.tool_call_id)
            if normalized_id and normalized_id != msg.tool_call_id:
                new_msg = msg.model_copy(update={"tool_call_id": normalized_id})
                transformed.append(new_msg)
            else:
                transformed.append(msg)
            continue

        # Assistant messages need transformation
        if msg.role == "assistant":
            assistant_msg = msg
            is_same_model = (
                assistant_msg.provider == model.provider
                and assistant_msg.api == model.api
                and assistant_msg.model == model.id
            )

            transformed_content = []
            for block in assistant_msg.content:
                if block.type == "thinking":
                    # For same model: keep thinking blocks with signatures
                    if is_same_model and block.thinking_signature:
                        transformed_content.append(block)
                    # Skip empty thinking blocks
                    elif not block.thinking or block.thinking.strip() == "":
                        continue
                    elif is_same_model:
                        transformed_content.append(block)
                    else:
                        # Convert to plain text for other models
                        transformed_content.append(
                            TextContent(type="text", text=block.thinking)
                        )

                elif block.type == "text":
                    if is_same_model:
                        transformed_content.append(block)
                    else:
                        transformed_content.append(
                            TextContent(type="text", text=block.text)
                        )

                elif block.type == "toolCall":
                    tool_call = block
                    normalized_tool_call = tool_call

                    # Remove thought signature for different models
                    if not is_same_model and tool_call.thought_signature:
                        normalized_tool_call = tool_call.model_copy(
                            update={"thought_signature": None}
                        )

                    # Normalize tool call ID
                    if not is_same_model and normalize_tool_call_id:
                        normalized_id = normalize_tool_call_id(
                            tool_call.id, model, assistant_msg
                        )
                        if normalized_id != tool_call.id:
                            tool_call_id_map[tool_call.id] = normalized_id
                            normalized_tool_call = normalized_tool_call.model_copy(
                                update={"id": normalized_id}
                            )

                    transformed_content.append(normalized_tool_call)

                else:
                    transformed_content.append(block)

            new_assistant_msg = assistant_msg.model_copy(
                update={"content": transformed_content}
            )
            transformed.append(new_assistant_msg)
            continue

        # Pass through unknown message types
        transformed.append(msg)

    # Second pass: insert synthetic empty tool results for orphaned tool calls
    result: list[Message] = []
    pending_tool_calls: list[ToolCall] = []
    existing_tool_result_ids: set[str] = set()

    for msg in transformed:
        if msg.role == "assistant":
            # If we have pending orphaned tool calls, insert synthetic results
            if pending_tool_calls:
                for tc in pending_tool_calls:
                    if tc.id not in existing_tool_result_ids:
                        result.append(
                            ToolResultMessage(
                                role="toolResult",
                                tool_call_id=tc.id,
                                tool_name=tc.name,
                                content=[TextContent(type="text", text="No result provided")],
                                is_error=True,
                                timestamp=int(time.time() * 1000),
                            )
                        )
                pending_tool_calls = []
                existing_tool_result_ids = set()

            # Skip errored/aborted assistant messages
            assistant_msg = msg
            if assistant_msg.stop_reason in ("error", "aborted"):
                continue

            # Track tool calls from this assistant message
            tool_calls = [b for b in assistant_msg.content if b.type == "toolCall"]
            if tool_calls:
                pending_tool_calls = tool_calls  # type: ignore
                existing_tool_result_ids = set()

            result.append(msg)

        elif msg.role == "toolResult":
            existing_tool_result_ids.add(msg.tool_call_id)
            result.append(msg)

        elif msg.role == "user":
            # User message interrupts tool flow - insert synthetic results
            if pending_tool_calls:
                for tc in pending_tool_calls:
                    if tc.id not in existing_tool_result_ids:
                        result.append(
                            ToolResultMessage(
                                role="toolResult",
                                tool_call_id=tc.id,
                                tool_name=tc.name,
                                content=[TextContent(type="text", text="No result provided")],
                                is_error=True,
                                timestamp=int(time.time() * 1000),
                            )
                        )
                pending_tool_calls = []
                existing_tool_result_ids = set()
            result.append(msg)

        else:
            result.append(msg)

    return result
