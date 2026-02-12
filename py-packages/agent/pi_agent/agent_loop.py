"""
Agent loop that works with AgentMessage throughout.
Transforms to Message[] only at the LLM call boundary.
"""

from __future__ import annotations

import asyncio
import time
from typing import Any

from pi_ai import (
    AssistantMessage,
    Context,
    EventStream,
    TextContent,
    ToolResultMessage,
    stream_simple,
    validate_tool_arguments,
)

from pi_agent.types import (
    AgentContext,
    AgentEndEvent,
    AgentEvent,
    AgentLoopConfig,
    AgentMessage,
    AgentStartEvent,
    AgentTool,
    AgentToolResult,
    MessageEndEvent,
    MessageStartEvent,
    MessageUpdateEvent,
    StreamFn,
    ToolExecutionEndEvent,
    ToolExecutionStartEvent,
    ToolExecutionUpdateEvent,
    TurnEndEvent,
    TurnStartEvent,
)


def _create_agent_stream() -> EventStream[AgentEvent, list[AgentMessage]]:
    """Create an agent event stream."""
    return EventStream[AgentEvent, list[AgentMessage]](
        is_complete=lambda event: event.type == "agent_end",
        extract_result=lambda event: event.messages if event.type == "agent_end" else [],
    )


def agent_loop(
    prompts: list[AgentMessage],
    context: AgentContext,
    config: AgentLoopConfig,
    signal: Any | None = None,
    stream_fn: StreamFn | None = None,
) -> EventStream[AgentEvent, list[AgentMessage]]:
    """
    Start an agent loop with a new prompt message.
    
    The prompt is added to the context and events are emitted for it.
    """
    stream = _create_agent_stream()

    async def _run() -> None:
        new_messages: list[AgentMessage] = list(prompts)
        current_context = AgentContext(
            system_prompt=context.system_prompt,
            messages=list(context.messages) + list(prompts),
            tools=context.tools,
        )

        stream.push(AgentStartEvent())
        stream.push(TurnStartEvent())
        for prompt in prompts:
            stream.push(MessageStartEvent(message=prompt))
            stream.push(MessageEndEvent(message=prompt))

        await _run_loop(current_context, new_messages, config, signal, stream, stream_fn)

    asyncio.get_event_loop().create_task(_run())
    return stream


def agent_loop_continue(
    context: AgentContext,
    config: AgentLoopConfig,
    signal: Any | None = None,
    stream_fn: StreamFn | None = None,
) -> EventStream[AgentEvent, list[AgentMessage]]:
    """
    Continue an agent loop from the current context without adding a new message.
    
    Used for retries - context already has user message or tool results.
    """
    if not context.messages:
        raise ValueError("Cannot continue: no messages in context")

    if context.messages[-1].role == "assistant":
        raise ValueError("Cannot continue from message role: assistant")

    stream = _create_agent_stream()

    async def _run() -> None:
        new_messages: list[AgentMessage] = []
        current_context = AgentContext(
            system_prompt=context.system_prompt,
            messages=list(context.messages),
            tools=context.tools,
        )

        stream.push(AgentStartEvent())
        stream.push(TurnStartEvent())

        await _run_loop(current_context, new_messages, config, signal, stream, stream_fn)

    asyncio.get_event_loop().create_task(_run())
    return stream


async def _run_loop(
    current_context: AgentContext,
    new_messages: list[AgentMessage],
    config: AgentLoopConfig,
    signal: Any | None,
    stream: EventStream[AgentEvent, list[AgentMessage]],
    stream_fn: StreamFn | None = None,
) -> None:
    """Main loop logic shared by agent_loop and agent_loop_continue."""
    first_turn = True
    
    # Check for steering messages at start
    pending_messages: list[AgentMessage] = []
    if config.get_steering_messages:
        pending_messages = await config.get_steering_messages()

    # Outer loop: continues when queued follow-up messages arrive
    while True:
        has_more_tool_calls = True
        steering_after_tools: list[AgentMessage] | None = None

        # Inner loop: process tool calls and steering messages
        while has_more_tool_calls or pending_messages:
            if not first_turn:
                stream.push(TurnStartEvent())
            else:
                first_turn = False

            # Process pending messages
            if pending_messages:
                for message in pending_messages:
                    stream.push(MessageStartEvent(message=message))
                    stream.push(MessageEndEvent(message=message))
                    current_context.messages.append(message)
                    new_messages.append(message)
                pending_messages = []

            # Stream assistant response
            message = await _stream_assistant_response(
                current_context, config, signal, stream, stream_fn
            )
            new_messages.append(message)

            if message.stop_reason in ("error", "aborted"):
                stream.push(TurnEndEvent(message=message, tool_results=[]))
                stream.push(AgentEndEvent(messages=new_messages))
                stream.end(new_messages)
                return

            # Check for tool calls
            tool_calls = [c for c in message.content if c.type == "toolCall"]
            has_more_tool_calls = len(tool_calls) > 0

            tool_results: list[ToolResultMessage] = []
            if has_more_tool_calls:
                execution = await _execute_tool_calls(
                    current_context.tools,
                    message,
                    signal,
                    stream,
                    config.get_steering_messages,
                )
                tool_results = execution["tool_results"]
                steering_after_tools = execution.get("steering_messages")

                for result in tool_results:
                    current_context.messages.append(result)
                    new_messages.append(result)

            stream.push(TurnEndEvent(message=message, tool_results=tool_results))

            # Get steering messages after turn completes
            if steering_after_tools:
                pending_messages = steering_after_tools
                steering_after_tools = None
            elif config.get_steering_messages:
                pending_messages = await config.get_steering_messages()

        # Agent would stop here. Check for follow-up messages.
        if config.get_follow_up_messages:
            follow_up_messages = await config.get_follow_up_messages()
            if follow_up_messages:
                pending_messages = follow_up_messages
                continue

        # No more messages, exit
        break

    stream.push(AgentEndEvent(messages=new_messages))
    stream.end(new_messages)


async def _stream_assistant_response(
    context: AgentContext,
    config: AgentLoopConfig,
    signal: Any | None,
    stream: EventStream[AgentEvent, list[AgentMessage]],
    stream_fn: StreamFn | None = None,
) -> AssistantMessage:
    """Stream an assistant response from the LLM."""
    # Apply context transform if configured
    messages = context.messages
    if config.transform_context:
        messages = await config.transform_context(messages, signal)

    # Convert to LLM-compatible messages
    convert_result = config.convert_to_llm(messages)
    if asyncio.iscoroutine(convert_result):
        llm_messages = await convert_result
    else:
        llm_messages = convert_result

    # Build LLM context
    llm_context = Context(
        system_prompt=context.system_prompt,
        messages=llm_messages,
        tools=[
            {"name": t.name, "description": t.description, "parameters": t.parameters}
            for t in (context.tools or [])
        ] if context.tools else None,
    )

    fn = stream_fn or stream_simple

    # Resolve API key
    resolved_api_key = config.api_key
    if config.get_api_key:
        key_result = config.get_api_key(config.model.provider)
        if asyncio.iscoroutine(key_result):
            resolved_api_key = await key_result or config.api_key
        else:
            resolved_api_key = key_result or config.api_key

    # Create options
    from pi_ai import SimpleStreamOptions

    options = SimpleStreamOptions(
        temperature=config.temperature,
        max_tokens=config.max_tokens,
        api_key=resolved_api_key,
        cache_retention=config.cache_retention,
        session_id=config.session_id,
        headers=config.headers,
        reasoning=config.reasoning,
        thinking_budgets=config.thinking_budgets,
        max_retry_delay_ms=config.max_retry_delay_ms,
    )

    response = fn(config.model, llm_context, options)

    partial_message: AssistantMessage | None = None
    added_partial = False

    async for event in response:
        if event.type == "start":
            partial_message = event.partial
            context.messages.append(partial_message)
            added_partial = True
            stream.push(MessageStartEvent(message=partial_message.model_copy()))

        elif event.type in (
            "text_start", "text_delta", "text_end",
            "thinking_start", "thinking_delta", "thinking_end",
            "toolcall_start", "toolcall_delta", "toolcall_end",
        ):
            if partial_message:
                partial_message = event.partial
                context.messages[-1] = partial_message
                stream.push(MessageUpdateEvent(
                    message=partial_message.model_copy(),
                    assistant_message_event=event,
                ))

        elif event.type in ("done", "error"):
            final_message = await response.result()
            if added_partial:
                context.messages[-1] = final_message
            else:
                context.messages.append(final_message)
            if not added_partial:
                stream.push(MessageStartEvent(message=final_message.model_copy()))
            stream.push(MessageEndEvent(message=final_message))
            return final_message

    return await response.result()


async def _execute_tool_calls(
    tools: list[AgentTool] | None,
    assistant_message: AssistantMessage,
    signal: Any | None,
    stream: EventStream[AgentEvent, list[AgentMessage]],
    get_steering_messages: Any | None = None,
) -> dict[str, Any]:
    """Execute tool calls from an assistant message."""
    tool_calls = [c for c in assistant_message.content if c.type == "toolCall"]
    results: list[ToolResultMessage] = []
    steering_messages: list[AgentMessage] | None = None

    for index, tool_call in enumerate(tool_calls):
        tool = next((t for t in (tools or []) if t.name == tool_call.name), None)

        stream.push(ToolExecutionStartEvent(
            tool_call_id=tool_call.id,
            tool_name=tool_call.name,
            args=tool_call.arguments,
        ))

        result: AgentToolResult
        is_error = False

        try:
            if not tool:
                raise ValueError(f"Tool {tool_call.name} not found")

            validated_args = validate_tool_arguments(tool, tool_call)

            def on_update(partial_result: AgentToolResult) -> None:
                stream.push(ToolExecutionUpdateEvent(
                    tool_call_id=tool_call.id,
                    tool_name=tool_call.name,
                    args=tool_call.arguments,
                    partial_result=partial_result,
                ))

            result = await tool.execute(tool_call.id, validated_args, signal, on_update)

        except Exception as e:
            result = AgentToolResult(
                content=[TextContent(type="text", text=str(e))],
                details={},
            )
            is_error = True

        stream.push(ToolExecutionEndEvent(
            tool_call_id=tool_call.id,
            tool_name=tool_call.name,
            result=result,
            is_error=is_error,
        ))

        tool_result_message = ToolResultMessage(
            role="toolResult",
            tool_call_id=tool_call.id,
            tool_name=tool_call.name,
            content=result.content,
            details=result.details,
            is_error=is_error,
            timestamp=int(time.time() * 1000),
        )

        results.append(tool_result_message)
        stream.push(MessageStartEvent(message=tool_result_message))
        stream.push(MessageEndEvent(message=tool_result_message))

        # Check for steering messages
        if get_steering_messages:
            steering = await get_steering_messages()
            if steering:
                steering_messages = steering
                # Skip remaining tools
                for skipped in tool_calls[index + 1:]:
                    results.append(_skip_tool_call(skipped, stream))
                break

    return {"tool_results": results, "steering_messages": steering_messages}


def _skip_tool_call(
    tool_call: Any,
    stream: EventStream[AgentEvent, list[AgentMessage]],
) -> ToolResultMessage:
    """Skip a tool call due to queued user message."""
    result = AgentToolResult(
        content=[TextContent(type="text", text="Skipped due to queued user message.")],
        details={},
    )

    stream.push(ToolExecutionStartEvent(
        tool_call_id=tool_call.id,
        tool_name=tool_call.name,
        args=tool_call.arguments,
    ))
    stream.push(ToolExecutionEndEvent(
        tool_call_id=tool_call.id,
        tool_name=tool_call.name,
        result=result,
        is_error=True,
    ))

    tool_result_message = ToolResultMessage(
        role="toolResult",
        tool_call_id=tool_call.id,
        tool_name=tool_call.name,
        content=result.content,
        details={},
        is_error=True,
        timestamp=int(time.time() * 1000),
    )

    stream.push(MessageStartEvent(message=tool_result_message))
    stream.push(MessageEndEvent(message=tool_result_message))

    return tool_result_message
