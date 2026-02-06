"""
Agent loop implementation that works with AgentMessage throughout.
Transforms to Message[] only at the LLM call boundary.
"""

import asyncio
from typing import AsyncGenerator, List, Optional, Callable, Any
from .types import (
    AgentContext,
    AgentEvent,
    AgentLoopConfig,
    AgentMessage,
    AgentTool,
    AgentToolResult,
    StreamFn,
    AssistantMessage,
    ToolResultMessage,
    AgentStartEvent,
    AgentEndEvent,
    TurnStartEvent,
    TurnEndEvent,
    MessageStartEvent,
    MessageEndEvent,
    ToolExecutionStartEvent,
    ToolExecutionUpdateEvent,
    ToolExecutionEndEvent,
)

class EventStream:
    """Simple event stream implementation."""
    
    def __init__(self, is_end_event: Callable[[AgentEvent], bool], get_result: Callable[[AgentEvent], Any]):
        self.events = []
        self.is_end_event = is_end_event
        self.get_result = get_result
        self._future = asyncio.Future()
        
    def push(self, event: AgentEvent):
        self.events.append(event)
        
    def end(self, result: Any = None):
        if not self._future.done():
            self._future.set_result(result)
            
    async def result(self) -> Any:
        return await self._future
        
    def __aiter__(self):
        return EventStreamIterator(self)

class EventStreamIterator:
    def __init__(self, stream: EventStream):
        self.stream = stream
        self.index = 0
        
    def __aiter__(self):
        return self
        
    async def __anext__(self):
        while True:
            if self.index < len(self.stream.events):
                event = self.stream.events[self.index]
                self.index += 1
                return event
            elif self.stream._future.done():
                raise StopAsyncIteration
            else:
                await asyncio.sleep(0.01)  # Small delay to prevent busy waiting

def create_agent_stream() -> EventStream:
    """Create an agent event stream."""
    def is_end_event(event: AgentEvent) -> bool:
        return event.type == "agent_end"
        
    def get_result(event: AgentEvent) -> List[AgentMessage]:
        if event.type == "agent_end":
            return event.messages
        return []
        
    return EventStream(is_end_event, get_result)

async def agent_loop(
    prompts: List[AgentMessage],
    context: AgentContext,
    config: AgentLoopConfig,
    signal: Optional[asyncio.Event] = None,
    stream_fn: Optional[StreamFn] = None,
) -> EventStream:
    """
    Start an agent loop with a new prompt message.
    The prompt is added to the context and events are emitted for it.
    """
    stream = create_agent_stream()
    
    async def run():
        new_messages: List[AgentMessage] = list(prompts)
        current_context: AgentContext = AgentContext(
            systemPrompt=context.systemPrompt,
            messages=list(context.messages) + list(prompts),
            tools=context.tools
        )
        
        stream.push(AgentStartEvent())
        stream.push(TurnStartEvent())
        
        for prompt in prompts:
            stream.push(MessageStartEvent(message=prompt))
            stream.push(MessageEndEvent(message=prompt))
            
        await run_loop(current_context, new_messages, config, signal, stream, stream_fn)
        
    asyncio.create_task(run())
    return stream

async def agent_loop_continue(
    context: AgentContext,
    config: AgentLoopConfig,
    signal: Optional[asyncio.Event] = None,
    stream_fn: Optional[StreamFn] = None,
) -> EventStream:
    """
    Continue an agent loop from the current context without adding a new message.
    Used for retries - context already has user message or tool results.
    """
    if not context.messages:
        raise ValueError("Cannot continue: no messages in context")
        
    if context.messages[-1].role == "assistant":
        raise ValueError("Cannot continue from message role: assistant")
        
    stream = create_agent_stream()
    
    async def run():
        new_messages: List[AgentMessage] = []
        current_context: AgentContext = AgentContext(
            systemPrompt=context.systemPrompt,
            messages=list(context.messages),
            tools=context.tools
        )
        
        stream.push(AgentStartEvent())
        stream.push(TurnStartEvent())
        
        await run_loop(current_context, new_messages, config, signal, stream, stream_fn)
        
    asyncio.create_task(run())
    return stream

async def run_loop(
    current_context: AgentContext,
    new_messages: List[AgentMessage],
    config: AgentLoopConfig,
    signal: Optional[asyncio.Event],
    stream: EventStream,
    stream_fn: Optional[StreamFn],
):
    """Main loop logic shared by agent_loop and agent_loop_continue."""
    first_turn = True
    
    # Check for steering messages at start
    pending_messages: List[AgentMessage] = []
    if config.get_steering_messages:
        pending_messages = await config.get_steering_messages() or []
    
    # Outer loop: continues when queued follow-up messages arrive
    while True:
        has_more_tool_calls = True
        steering_after_tools: Optional[List[AgentMessage]] = None
        
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
            message = await stream_assistant_response(
                current_context, config, signal, stream, stream_fn
            )
            new_messages.append(message)
            
            if message.stopReason in ("error", "aborted"):
                stream.push(TurnEndEvent(message=message, toolResults=[]))
                stream.push(AgentEndEvent(messages=new_messages))
                stream.end(new_messages)
                return
                
            # Check for tool calls
            tool_calls = [c for c in message.content if c.type == "toolCall"]
            has_more_tool_calls = len(tool_calls) > 0
            
            tool_results: List[ToolResultMessage] = []
            if has_more_tool_calls:
                tool_execution = await execute_tool_calls(
                    current_context.tools,
                    message,
                    signal,
                    stream,
                    config.get_steering_messages,
                )
                tool_results.extend(tool_execution["toolResults"])
                steering_after_tools = tool_execution.get("steeringMessages")
                
                for result in tool_results:
                    current_context.messages.append(result)
                    new_messages.append(result)
                    
            stream.push(TurnEndEvent(message=message, toolResults=tool_results))
            
            # Get steering messages after turn completes
            if steering_after_tools and steering_after_tools:
                pending_messages = steering_after_tools
                steering_after_tools = None
            elif config.get_steering_messages:
                pending_messages = await config.get_steering_messages() or []
            else:
                pending_messages = []
                
        # Agent would stop here. Check for follow-up messages.
        follow_up_messages: List[AgentMessage] = []
        if config.get_follow_up_messages:
            follow_up_messages = await config.get_follow_up_messages() or []
            
        if follow_up_messages:
            # Set as pending so inner loop processes them
            pending_messages = follow_up_messages
            continue
            
        # No more messages, exit
        break
        
    stream.push(AgentEndEvent(messages=new_messages))
    stream.end(new_messages)

async def stream_assistant_response(
    context: AgentContext,
    config: AgentLoopConfig,
    signal: Optional[asyncio.Event],
    stream: EventStream,
    stream_fn: Optional[StreamFn],
) -> AssistantMessage:
    """
    Stream an assistant response from the LLM.
    This is where AgentMessage[] gets transformed to Message[] for the LLM.
    """
    # Apply context transform if configured
    messages = context.messages
    if config.transform_context:
        messages = await config.transform_context(messages, signal)
        
    # Convert to LLM-compatible messages
    llm_messages = await config.convert_to_llm(messages) if asyncio.iscoroutinefunction(config.convert_to_llm) else config.convert_to_llm(messages)
    
    # Build LLM context (simplified - would need actual pi-ai Context type)
    llm_context = {
        "systemPrompt": context.systemPrompt,
        "messages": llm_messages,
        "tools": context.tools,
    }
    
    # Resolve API key
    resolved_api_key = None
    if config.get_api_key:
        api_key_result = config.get_api_key(config.model.provider)  # type: ignore
        if asyncio.iscoroutine(api_key_result):
            resolved_api_key = await api_key_result
        else:
            resolved_api_key = api_key_result
            
    # Stream function (simplified)
    stream_function = stream_fn or default_stream_function
    
    response = await stream_function(config.model, llm_context, {
        "apiKey": resolved_api_key,
        "signal": signal,
    })
    
    partial_message: Optional[AssistantMessage] = None
    added_partial = False
    
    async for event in response:
        if event.type == "start":
            partial_message = event.partial
            context.messages.append(partial_message)
            added_partial = True
            stream.push(MessageStartEvent(message=partial_message))
        elif event.type in ("text_start", "text_delta", "text_end", 
                          "thinking_start", "thinking_delta", "thinking_end",
                          "toolcall_start", "toolcall_delta", "toolcall_end"):
            if partial_message:
                partial_message = event.partial
                context.messages[-1] = partial_message
                # Create simplified assistant message event for streaming
                assistant_event = type('AssistantMessageEvent', (), {
                    'type': event.type,
                    'partial': partial_message
                })()
                stream.push(type('MessageUpdateEvent', (), {
                    'type': 'message_update',
                    'assistantMessageEvent': assistant_event,
                    'message': partial_message
                })())
        elif event.type in ("done", "error"):
            final_message = await response.result()
            if added_partial:
                context.messages[-1] = final_message
            else:
                context.messages.append(final_message)
            if not added_partial:
                stream.push(MessageStartEvent(message=final_message))
            stream.push(MessageEndEvent(message=final_message))
            return final_message
            
    return await response.result()

async def execute_tool_calls(
    tools: Optional[List[AgentTool]],
    assistant_message: AssistantMessage,
    signal: Optional[asyncio.Event],
    stream: EventStream,
    get_steering_messages: Optional[Callable[[], Any]],
):
    """Execute tool calls from an assistant message."""
    tool_calls = [c for c in assistant_message.content if c.type == "toolCall"]
    results: List[ToolResultMessage] = []
    steering_messages: Optional[List[AgentMessage]] = None
    
    for index, tool_call in enumerate(tool_calls):
        tool = next((t for t in tools or [] if t.name == tool_call.name), None)
        
        stream.push(ToolExecutionStartEvent(
            toolCallId=tool_call.id,
            toolName=tool_call.name,
            args=tool_call.arguments
        ))
        
        result: AgentToolResult
        is_error = False
        
        try:
            if not tool:
                raise ValueError(f"Tool {tool_call.name} not found")
                
            # Validate arguments (simplified)
            validated_args = tool_call.arguments
            
            # Execute tool
            result = await tool.execute(tool_call.id, validated_args, signal, None)
        except Exception as e:
            result = AgentToolResult(
                content=[TextContent(text=str(e))],
                details={}
            )
            is_error = True
            
        stream.push(ToolExecutionEndEvent(
            toolCallId=tool_call.id,
            toolName=tool_call.name,
            result=result,
            isError=is_error
        ))
        
        tool_result_message = ToolResultMessage(
            role="toolResult",
            toolCallId=tool_call.id,
            toolName=tool_call.name,
            content=result.content,
            details=result.details,
            isError=is_error,
            timestamp=int(asyncio.get_event_loop().time() * 1000)
        )
        
        results.append(tool_result_message)
        stream.push(MessageStartEvent(message=tool_result_message))
        stream.push(MessageEndEvent(message=tool_result_message))
        
        # Check for steering messages
        if get_steering_messages:
            steering = await get_steering_messages() or []
            if steering:
                steering_messages = steering
                # Skip remaining calls
                remaining_calls = tool_calls[index + 1:]
                for skipped_call in remaining_calls:
                    results.append(skip_tool_call(skipped_call, stream))
                break
                
    return {"toolResults": results, "steeringMessages": steering_messages}

def skip_tool_call(tool_call, stream: EventStream) -> ToolResultMessage:
    """Skip a tool call due to queued user message."""
    result = AgentToolResult(
        content=[TextContent(text="Skipped due to queued user message.")],
        details={}
    )
    
    stream.push(ToolExecutionStartEvent(
        toolCallId=tool_call.id,
        toolName=tool_call.name,
        args=tool_call.arguments
    ))
    
    stream.push(ToolExecutionEndEvent(
        toolCallId=tool_call.id,
        toolName=tool_call.name,
        result=result,
        isError=True
    ))
    
    tool_result_message = ToolResultMessage(
        role="toolResult",
        toolCallId=tool_call.id,
        toolName=tool_call.name,
        content=result.content,
        details={},
        isError=True,
        timestamp=int(asyncio.get_event_loop().time() * 1000)
    )
    
    stream.push(MessageStartEvent(message=tool_result_message))
    stream.push(MessageEndEvent(message=tool_result_message))
    
    return tool_result_message

# Placeholder for default stream function
async def default_stream_function(model, context, options):
    """Placeholder for the actual stream function from pi-ai."""
    # This would be implemented to call the actual LLM streaming API
    class MockResponse:
        async def __aiter__(self):
            yield type('Event', (), {'type': 'start', 'partial': AssistantMessage(role='assistant')})()
            yield type('Event', (), {'type': 'done'})()
            
        async def result(self):
            return AssistantMessage(role='assistant', content=[TextContent(text="Mock response")])
            
    return MockResponse()