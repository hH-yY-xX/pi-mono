"""
Agent class that uses the agent-loop directly.
"""

from __future__ import annotations

import asyncio
import time
from typing import Any, Callable

from pydantic import BaseModel, ConfigDict, Field

from pi_ai import (
    AssistantMessage,
    ImageContent,
    Message,
    Model,
    TextContent,
    ThinkingBudgets,
    Usage,
    UsageCost,
    get_model,
    stream_simple,
)

from pi_agent.agent_loop import agent_loop, agent_loop_continue
from pi_agent.types import (
    AgentContext,
    AgentEvent,
    AgentLoopConfig,
    AgentMessage,
    AgentState,
    AgentTool,
    StreamFn,
    ThinkingLevel,
)


def _default_convert_to_llm(messages: list[AgentMessage]) -> list[Message]:
    """Default convertToLlm: Keep only LLM-compatible messages."""
    return [m for m in messages if m.role in ("user", "assistant", "toolResult")]


class AgentOptions(BaseModel):
    """Options for creating an Agent."""

    model_config = ConfigDict(extra="forbid", arbitrary_types_allowed=True)

    initial_state: AgentState | None = None
    """Initial state for the agent."""

    convert_to_llm: Callable[[list[AgentMessage]], list[Message]] | None = None
    """Converts AgentMessage[] to LLM-compatible Message[] before each LLM call."""

    transform_context: Callable[
        [list[AgentMessage], Any | None], "asyncio.Future[list[AgentMessage]]"
    ] | None = None
    """Optional transform applied to context before convert_to_llm."""

    steering_mode: str = "one-at-a-time"
    """Steering mode: 'all' or 'one-at-a-time'."""

    follow_up_mode: str = "one-at-a-time"
    """Follow-up mode: 'all' or 'one-at-a-time'."""

    stream_fn: StreamFn | None = None
    """Custom stream function."""

    session_id: str | None = None
    """Optional session identifier."""

    get_api_key: Callable[[str], str | None] | None = None
    """Resolves an API key dynamically."""

    thinking_budgets: ThinkingBudgets | None = None
    """Custom token budgets for thinking levels."""

    max_retry_delay_ms: int | None = None
    """Maximum delay to wait for server-requested retries."""


class Agent:
    """
    Agent class that uses the agent-loop directly.
    No transport abstraction - calls stream_simple via the loop.
    """

    def __init__(self, opts: AgentOptions | None = None) -> None:
        opts = opts or AgentOptions()

        # Initialize default state
        default_model = get_model("google", "gemini-2.5-flash-lite-preview-06-17")
        if not default_model:
            # Fallback if model not found
            from pi_ai import Model, ModelCost

            default_model = Model(
                id="gemini-2.5-flash-lite-preview-06-17",
                name="Gemini 2.5 Flash Lite",
                api="google-generative-ai",
                provider="google",
                base_url="https://generativelanguage.googleapis.com",
                reasoning=False,
                input=["text", "image"],
                cost=ModelCost(input=0, output=0, cache_read=0, cache_write=0),
                context_window=1000000,
                max_tokens=8192,
            )

        self._state = AgentState(
            system_prompt="",
            model=default_model,
            thinking_level="off",
            tools=[],
            messages=[],
            is_streaming=False,
            stream_message=None,
            pending_tool_calls=set(),
            error=None,
        )

        if opts.initial_state:
            self._state = opts.initial_state

        self._listeners: set[Callable[[AgentEvent], None]] = set()
        self._abort_controller: asyncio.Event | None = None
        self._convert_to_llm = opts.convert_to_llm or _default_convert_to_llm
        self._transform_context = opts.transform_context
        self._steering_queue: list[AgentMessage] = []
        self._follow_up_queue: list[AgentMessage] = []
        self._steering_mode = opts.steering_mode
        self._follow_up_mode = opts.follow_up_mode
        self.stream_fn = opts.stream_fn or stream_simple
        self._session_id = opts.session_id
        self.get_api_key = opts.get_api_key
        self._running_prompt: asyncio.Future[None] | None = None
        self._thinking_budgets = opts.thinking_budgets
        self._max_retry_delay_ms = opts.max_retry_delay_ms

    @property
    def session_id(self) -> str | None:
        """Get the current session ID."""
        return self._session_id

    @session_id.setter
    def session_id(self, value: str | None) -> None:
        """Set the session ID."""
        self._session_id = value

    @property
    def thinking_budgets(self) -> ThinkingBudgets | None:
        """Get the current thinking budgets."""
        return self._thinking_budgets

    @thinking_budgets.setter
    def thinking_budgets(self, value: ThinkingBudgets | None) -> None:
        """Set custom thinking budgets."""
        self._thinking_budgets = value

    @property
    def max_retry_delay_ms(self) -> int | None:
        """Get the current max retry delay."""
        return self._max_retry_delay_ms

    @max_retry_delay_ms.setter
    def max_retry_delay_ms(self, value: int | None) -> None:
        """Set the maximum retry delay."""
        self._max_retry_delay_ms = value

    @property
    def state(self) -> AgentState:
        """Get the current agent state."""
        return self._state

    def subscribe(self, fn: Callable[[AgentEvent], None]) -> Callable[[], None]:
        """Subscribe to agent events."""
        self._listeners.add(fn)
        return lambda: self._listeners.discard(fn)

    # State mutators
    def set_system_prompt(self, prompt: str) -> None:
        """Set the system prompt."""
        self._state.system_prompt = prompt

    def set_model(self, model: Model) -> None:
        """Set the model."""
        self._state.model = model

    def set_thinking_level(self, level: ThinkingLevel) -> None:
        """Set the thinking level."""
        self._state.thinking_level = level

    def set_steering_mode(self, mode: str) -> None:
        """Set steering mode."""
        self._steering_mode = mode

    def get_steering_mode(self) -> str:
        """Get steering mode."""
        return self._steering_mode

    def set_follow_up_mode(self, mode: str) -> None:
        """Set follow-up mode."""
        self._follow_up_mode = mode

    def get_follow_up_mode(self) -> str:
        """Get follow-up mode."""
        return self._follow_up_mode

    def set_tools(self, tools: list[AgentTool]) -> None:
        """Set the tools."""
        self._state.tools = tools

    def replace_messages(self, messages: list[AgentMessage]) -> None:
        """Replace all messages."""
        self._state.messages = list(messages)

    def append_message(self, message: AgentMessage) -> None:
        """Append a message."""
        self._state.messages = [*self._state.messages, message]

    def steer(self, message: AgentMessage) -> None:
        """Queue a steering message to interrupt the agent mid-run."""
        self._steering_queue.append(message)

    def follow_up(self, message: AgentMessage) -> None:
        """Queue a follow-up message."""
        self._follow_up_queue.append(message)

    def clear_steering_queue(self) -> None:
        """Clear the steering queue."""
        self._steering_queue = []

    def clear_follow_up_queue(self) -> None:
        """Clear the follow-up queue."""
        self._follow_up_queue = []

    def clear_all_queues(self) -> None:
        """Clear all queues."""
        self._steering_queue = []
        self._follow_up_queue = []

    def clear_messages(self) -> None:
        """Clear all messages."""
        self._state.messages = []

    def abort(self) -> None:
        """Abort the current operation."""
        if self._abort_controller:
            self._abort_controller.set()

    async def wait_for_idle(self) -> None:
        """Wait for the agent to become idle."""
        if self._running_prompt:
            await self._running_prompt

    def reset(self) -> None:
        """Reset the agent state."""
        self._state.messages = []
        self._state.is_streaming = False
        self._state.stream_message = None
        self._state.pending_tool_calls = set()
        self._state.error = None
        self._steering_queue = []
        self._follow_up_queue = []

    async def prompt(
        self,
        input_: str | AgentMessage | list[AgentMessage],
        images: list[ImageContent] | None = None,
    ) -> None:
        """Send a prompt to the agent."""
        if self._state.is_streaming:
            raise RuntimeError(
                "Agent is already processing a prompt. Use steer() or follow_up() "
                "to queue messages, or wait for completion."
            )

        model = self._state.model
        if not model:
            raise RuntimeError("No model configured")

        msgs: list[AgentMessage]

        if isinstance(input_, list):
            msgs = input_
        elif isinstance(input_, str):
            content: list[TextContent | ImageContent] = [TextContent(type="text", text=input_)]
            if images:
                content.extend(images)
            from pi_ai import UserMessage

            msgs = [
                UserMessage(
                    role="user",
                    content=content,
                    timestamp=int(time.time() * 1000),
                )
            ]
        else:
            msgs = [input_]

        await self._run_loop(msgs)

    async def continue_(self) -> None:
        """Continue from current context (for retry after overflow)."""
        if self._state.is_streaming:
            raise RuntimeError("Agent is already processing. Wait for completion before continuing.")

        messages = self._state.messages
        if not messages:
            raise RuntimeError("No messages to continue from")
        if messages[-1].role == "assistant":
            raise RuntimeError("Cannot continue from message role: assistant")

        await self._run_loop(None)

    async def _run_loop(self, messages: list[AgentMessage] | None) -> None:
        """Run the agent loop."""
        model = self._state.model
        if not model:
            raise RuntimeError("No model configured")

        loop = asyncio.get_event_loop()
        self._running_prompt = loop.create_future()
        self._abort_controller = asyncio.Event()
        self._state.is_streaming = True
        self._state.stream_message = None
        self._state.error = None

        reasoning = None if self._state.thinking_level == "off" else self._state.thinking_level

        context = AgentContext(
            system_prompt=self._state.system_prompt,
            messages=list(self._state.messages),
            tools=self._state.tools,
        )

        async def get_steering_messages() -> list[AgentMessage]:
            if self._steering_mode == "one-at-a-time":
                if self._steering_queue:
                    first = self._steering_queue[0]
                    self._steering_queue = self._steering_queue[1:]
                    return [first]
                return []
            else:
                steering = list(self._steering_queue)
                self._steering_queue = []
                return steering

        async def get_follow_up_messages() -> list[AgentMessage]:
            if self._follow_up_mode == "one-at-a-time":
                if self._follow_up_queue:
                    first = self._follow_up_queue[0]
                    self._follow_up_queue = self._follow_up_queue[1:]
                    return [first]
                return []
            else:
                follow_up = list(self._follow_up_queue)
                self._follow_up_queue = []
                return follow_up

        config = AgentLoopConfig(
            model=model,
            reasoning=reasoning,
            session_id=self._session_id,
            thinking_budgets=self._thinking_budgets,
            max_retry_delay_ms=self._max_retry_delay_ms,
            convert_to_llm=self._convert_to_llm,
            transform_context=self._transform_context,
            get_api_key=self.get_api_key,
            get_steering_messages=get_steering_messages,
            get_follow_up_messages=get_follow_up_messages,
        )

        partial: AgentMessage | None = None

        try:
            stream = (
                agent_loop(messages, context, config, self._abort_controller, self.stream_fn)
                if messages
                else agent_loop_continue(context, config, self._abort_controller, self.stream_fn)
            )

            async for event in stream:
                # Update internal state based on events
                if event.type == "message_start":
                    partial = event.message
                    self._state.stream_message = event.message

                elif event.type == "message_update":
                    partial = event.message
                    self._state.stream_message = event.message

                elif event.type == "message_end":
                    partial = None
                    self._state.stream_message = None
                    self.append_message(event.message)

                elif event.type == "tool_execution_start":
                    s = set(self._state.pending_tool_calls)
                    s.add(event.tool_call_id)
                    self._state.pending_tool_calls = s

                elif event.type == "tool_execution_end":
                    s = set(self._state.pending_tool_calls)
                    s.discard(event.tool_call_id)
                    self._state.pending_tool_calls = s

                elif event.type == "turn_end":
                    if (event.message.role == "assistant" and
                            hasattr(event.message, "error_message") and
                            event.message.error_message):
                        self._state.error = event.message.error_message

                elif event.type == "agent_end":
                    self._state.is_streaming = False
                    self._state.stream_message = None

                # Emit to listeners
                self._emit(event)

            # Handle any remaining partial message
            if (partial and partial.role == "assistant" and
                    hasattr(partial, "content") and partial.content):
                only_empty = not any(
                    (c.type == "thinking" and c.thinking.strip()) or
                    (c.type == "text" and c.text.strip()) or
                    (c.type == "toolCall" and c.name.strip())
                    for c in partial.content
                )
                if not only_empty:
                    self.append_message(partial)
                elif self._abort_controller and self._abort_controller.is_set():
                    raise RuntimeError("Request was aborted")

        except Exception as e:
            error_msg = AssistantMessage(
                role="assistant",
                content=[TextContent(type="text", text="")],
                api=model.api,
                provider=model.provider,
                model=model.id,
                usage=Usage(),
                stop_reason="aborted" if self._abort_controller and self._abort_controller.is_set() else "error",
                error_message=str(e),
                timestamp=int(time.time() * 1000),
            )

            self.append_message(error_msg)
            self._state.error = str(e)
            from pi_agent.types import AgentEndEvent

            self._emit(AgentEndEvent(messages=[error_msg]))

        finally:
            self._state.is_streaming = False
            self._state.stream_message = None
            self._state.pending_tool_calls = set()
            self._abort_controller = None
            if self._running_prompt and not self._running_prompt.done():
                self._running_prompt.set_result(None)
            self._running_prompt = None

    def _emit(self, event: AgentEvent) -> None:
        """Emit an event to all listeners."""
        for listener in self._listeners:
            listener(event)
