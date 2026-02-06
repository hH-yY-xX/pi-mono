"""
Agent class that uses the agent-loop directly.
No transport abstraction - calls stream function via the loop.
"""

import asyncio
from typing import List, Optional, Callable, Any, Union
from .types import (
    AgentContext,
    AgentEvent,
    AgentLoopConfig,
    AgentMessage,
    AgentState,
    AgentTool,
    StreamFn,
    ThinkingLevel,
    UserMessage,
    TextContent,
    ImageContent,
    Usage,
)
from .agent_loop import agent_loop, agent_loop_continue

def default_convert_to_llm(messages: List[AgentMessage]) -> List[Any]:
    """Default convertToLlm: Keep only LLM-compatible messages."""
    filtered = []
    for msg in messages:
        if hasattr(msg, 'role') and msg.role in ('user', 'assistant', 'toolResult'):
            filtered.append(msg)
    return filtered

class AgentOptions:
    def __init__(
        self,
        initial_state: Optional[dict] = None,
        convert_to_llm: Optional[Callable[[List[AgentMessage]], Union[List[Any], asyncio.Future[List[Any]]]]] = None,
        transform_context: Optional[Callable[[List[AgentMessage], Optional[asyncio.Event]], asyncio.Future[List[AgentMessage]]]] = None,
        steering_mode: str = "one-at-a-time",
        follow_up_mode: str = "one-at-a-time",
        stream_fn: Optional[StreamFn] = None,
        session_id: Optional[str] = None,
        get_api_key: Optional[Callable[[str], Union[str, asyncio.Future[str], None]]] = None,
        thinking_budgets: Optional[dict] = None,
        max_retry_delay_ms: Optional[int] = None,
    ):
        self.initial_state = initial_state or {}
        self.convert_to_llm = convert_to_llm
        self.transform_context = transform_context
        self.steering_mode = steering_mode
        self.follow_up_mode = follow_up_mode
        self.stream_fn = stream_fn
        self.session_id = session_id
        self.get_api_key = get_api_key
        self.thinking_budgets = thinking_budgets
        self.max_retry_delay_ms = max_retry_delay_ms

class Agent:
    def __init__(self, opts: AgentOptions = None):
        if opts is None:
            opts = AgentOptions()
            
        self._state = AgentState(
            systemPrompt="",
            model=None,  # Would be initialized with actual model
            thinkingLevel="off",
            tools=[],
            messages=[],
            isStreaming=False,
            streamMessage=None,
            pendingToolCalls=set(),
            error=None,
        )
        
        # Update with initial state
        for key, value in opts.initial_state.items():
            if hasattr(self._state, key):
                setattr(self._state, key, value)
                
        self.listeners = set()
        self.abort_controller = None
        self.convert_to_llm = opts.convert_to_llm or default_convert_to_llm
        self.transform_context = opts.transform_context
        self.steering_queue = []
        self.follow_up_queue = []
        self.steering_mode = opts.steering_mode
        self.follow_up_mode = opts.follow_up_mode
        self.stream_fn = opts.stream_fn
        self._session_id = opts.session_id
        self.get_api_key = opts.get_api_key
        self.running_prompt = None
        self.resolve_running_prompt = None
        self._thinking_budgets = opts.thinking_budgets
        self._max_retry_delay_ms = opts.max_retry_delay_ms

    @property
    def session_id(self) -> Optional[str]:
        """Get the current session ID used for provider caching."""
        return self._session_id

    @session_id.setter
    def session_id(self, value: Optional[str]):
        """Set the session ID for provider caching."""
        self._session_id = value

    @property
    def thinking_budgets(self) -> Optional[dict]:
        """Get the current thinking budgets."""
        return self._thinking_budgets

    @thinking_budgets.setter
    def thinking_budgets(self, value: Optional[dict]):
        """Set custom thinking budgets for token-based providers."""
        self._thinking_budgets = value

    @property
    def max_retry_delay_ms(self) -> Optional[int]:
        """Get the current max retry delay in milliseconds."""
        return self._max_retry_delay_ms

    @max_retry_delay_ms.setter
    def max_retry_delay_ms(self, value: Optional[int]):
        """Set the maximum delay to wait for server-requested retries."""
        self._max_retry_delay_ms = value

    @property
    def state(self) -> AgentState:
        """Get the current agent state."""
        return self._state

    def subscribe(self, fn: Callable[[AgentEvent], None]) -> Callable[[], None]:
        """Subscribe to agent events."""
        self.listeners.add(fn)
        return lambda: self.listeners.discard(fn)

    # State mutators
    def set_system_prompt(self, v: str):
        """Set the system prompt."""
        self._state.systemPrompt = v

    def set_model(self, m: Any):
        """Set the model."""
        self._state.model = m

    def set_thinking_level(self, l: ThinkingLevel):
        """Set the thinking level."""
        self._state.thinkingLevel = l

    def set_steering_mode(self, mode: str):
        """Set the steering mode."""
        self.steering_mode = mode

    def get_steering_mode(self) -> str:
        """Get the steering mode."""
        return self.steering_mode

    def set_follow_up_mode(self, mode: str):
        """Set the follow-up mode."""
        self.follow_up_mode = mode

    def get_follow_up_mode(self) -> str:
        """Get the follow-up mode."""
        return self.follow_up_mode

    def set_tools(self, t: List[AgentTool]):
        """Set the tools."""
        self._state.tools = t

    def replace_messages(self, ms: List[AgentMessage]):
        """Replace all messages."""
        self._state.messages = list(ms)

    def append_message(self, m: AgentMessage):
        """Append a message."""
        self._state.messages = list(self._state.messages) + [m]

    def steer(self, m: AgentMessage):
        """Queue a steering message to interrupt the agent mid-run."""
        self.steering_queue.append(m)

    def follow_up(self, m: AgentMessage):
        """Queue a follow-up message to be processed after the agent finishes."""
        self.follow_up_queue.append(m)

    def clear_steering_queue(self):
        """Clear the steering queue."""
        self.steering_queue = []

    def clear_follow_up_queue(self):
        """Clear the follow-up queue."""
        self.follow_up_queue = []

    def clear_all_queues(self):
        """Clear all queues."""
        self.steering_queue = []
        self.follow_up_queue = []

    def clear_messages(self):
        """Clear all messages."""
        self._state.messages = []

    def abort(self):
        """Abort the current operation."""
        if self.abort_controller:
            self.abort_controller.set()

    async def wait_for_idle(self) -> None:
        """Wait for the agent to become idle."""
        if self.running_prompt:
            await self.running_prompt

    def reset(self):
        """Reset the agent state."""
        self._state.messages = []
        self._state.isStreaming = False
        self._state.streamMessage = None
        self._state.pendingToolCalls = set()
        self._state.error = None
        self.steering_queue = []
        self.follow_up_queue = []

    async def prompt(self, input_data: Union[str, AgentMessage, List[AgentMessage]], images: Optional[List[ImageContent]] = None) -> None:
        """Send a prompt with an AgentMessage."""
        if self._state.isStreaming:
            raise RuntimeError(
                "Agent is already processing a prompt. Use steer() or followUp() to queue messages, or wait for completion."
            )

        if not self._state.model:
            raise RuntimeError("No model configured")

        if isinstance(input_data, list):
            msgs = input_data
        elif isinstance(input_data, str):
            content = [TextContent(text=input_data)]
            if images:
                content.extend(images)
            msgs = [UserMessage(
                role="user",
                content=content,
                timestamp=int(asyncio.get_event_loop().time() * 1000)
            )]
        else:
            msgs = [input_data]

        await self._run_loop(msgs)

    async def continue_(self) -> None:
        """Continue from current context (for retry after overflow)."""
        if self._state.isStreaming:
            raise RuntimeError("Agent is already processing. Wait for completion before continuing.")

        messages = self._state.messages
        if not messages:
            raise RuntimeError("No messages to continue from")
        if messages[-1].role == "assistant":  # type: ignore
            raise RuntimeError("Cannot continue from message role: assistant")

        await self._run_loop(None)

    async def _run_loop(self, messages: Optional[List[AgentMessage]] = None):
        """Run the agent loop."""
        if not self._state.model:
            raise RuntimeError("No model configured")

        # Create promise for running state
        loop = asyncio.get_event_loop()
        self.running_prompt = loop.create_future()
        
        self.abort_controller = asyncio.Event()
        self._state.isStreaming = True
        self._state.streamMessage = None
        self._state.error = None

        reasoning = None if self._state.thinkingLevel == "off" else self._state.thinkingLevel

        context = AgentContext(
            systemPrompt=self._state.systemPrompt,
            messages=list(self._state.messages),
            tools=self._state.tools,
        )

        config = AgentLoopConfig(
            model=self._state.model,
            convert_to_llm=self.convert_to_llm,
            transform_context=self.transform_context,
            get_api_key=self.get_api_key,
            get_steering_messages=self._get_steering_messages,
            get_follow_up_messages=self._get_follow_up_messages,
        )

        partial = None

        try:
            if messages:
                stream = agent_loop(messages, context, config, self.abort_controller, self.stream_fn)
            else:
                stream = agent_loop_continue(context, config, self.abort_controller, self.stream_fn)

            async for event in stream:
                # Update internal state based on events
                if event.type == "message_start":
                    partial = event.message
                    self._state.streamMessage = event.message
                elif event.type == "message_update":
                    partial = event.message
                    self._state.streamMessage = event.message
                elif event.type == "message_end":
                    partial = None
                    self._state.streamMessage = None
                    self.append_message(event.message)
                elif event.type == "tool_execution_start":
                    s = set(self._state.pendingToolCalls)
                    s.add(event.toolCallId)
                    self._state.pendingToolCalls = s
                elif event.type == "tool_execution_end":
                    s = set(self._state.pendingToolCalls)
                    s.discard(event.toolCallId)
                    self._state.pendingToolCalls = s
                elif event.type == "turn_end":
                    if hasattr(event.message, 'errorMessage') and event.message.errorMessage:
                        self._state.error = event.message.errorMessage
                elif event.type == "agent_end":
                    self._state.isStreaming = False
                    self._state.streamMessage = None

                # Emit to listeners
                self._emit(event)

            # Handle any remaining partial message
            if partial and partial.role == "assistant" and partial.content:  # type: ignore
                only_empty = not any(
                    (hasattr(c, 'thinking') and c.thinking.strip()) or  # type: ignore
                    (hasattr(c, 'text') and c.text.strip()) or  # type: ignore
                    (hasattr(c, 'name') and c.name.strip())  # type: ignore
                    for c in partial.content  # type: ignore
                )
                if not only_empty:
                    self.append_message(partial)
                elif self.abort_controller and self.abort_controller.is_set():
                    raise RuntimeError("Request was aborted")

        except Exception as err:
            error_msg = UserMessage(  # Using UserMessage as placeholder for error
                role="assistant",
                content=[TextContent(text="")],
                timestamp=int(asyncio.get_event_loop().time() * 1000)
            )
            # Add error attributes
            error_msg.errorMessage = str(err)  # type: ignore
            error_msg.stopReason = "aborted" if (self.abort_controller and self.abort_controller.is_set()) else "error"  # type: ignore
            
            self.append_message(error_msg)
            self._state.error = str(err)
            self._emit(AgentEndEvent(messages=[error_msg]))
        finally:
            self._state.isStreaming = False
            self._state.streamMessage = None
            self._state.pendingToolCalls = set()
            self.abort_controller = None
            if not self.running_prompt.done():
                self.running_prompt.set_result(None)
            self.running_prompt = None

    async def _get_steering_messages(self) -> List[AgentMessage]:
        """Get steering messages based on current mode."""
        if self.steering_mode == "one-at-a-time":
            if self.steering_queue:
                first = self.steering_queue[0]
                self.steering_queue = self.steering_queue[1:]
                return [first]
            return []
        else:
            steering = list(self.steering_queue)
            self.steering_queue = []
            return steering

    async def _get_follow_up_messages(self) -> List[AgentMessage]:
        """Get follow-up messages based on current mode."""
        if self.follow_up_mode == "one-at-a-time":
            if self.follow_up_queue:
                first = self.follow_up_queue[0]
                self.follow_up_queue = self.follow_up_queue[1:]
                return [first]
            return []
        else:
            follow_up = list(self.follow_up_queue)
            self.follow_up_queue = []
            return follow_up

    def _emit(self, e: AgentEvent):
        """Emit an event to all listeners."""
        for listener in self.listeners:
            listener(e)