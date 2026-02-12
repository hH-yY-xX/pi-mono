"""
Event stream classes for async iteration over LLM responses.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from typing import Callable, Generic, TypeVar

from pi_ai.types import AssistantMessage, AssistantMessageEvent

T = TypeVar("T")
R = TypeVar("R")


class EventStream(Generic[T, R]):
    """
    Generic event stream class for async iteration.
    
    Supports both async iteration and awaiting the final result.
    """

    def __init__(
        self,
        is_complete: Callable[[T], bool],
        extract_result: Callable[[T], R],
    ) -> None:
        self._queue: list[T] = []
        self._waiting: list[asyncio.Future[tuple[T | None, bool]]] = []
        self._done = False
        self._is_complete = is_complete
        self._extract_result = extract_result
        self._final_result_future: asyncio.Future[R] = asyncio.get_event_loop().create_future()

    def push(self, event: T) -> None:
        """Push an event to the stream."""
        if self._done:
            return

        if self._is_complete(event):
            self._done = True
            if not self._final_result_future.done():
                self._final_result_future.set_result(self._extract_result(event))

        # Deliver to waiting consumer or queue it
        if self._waiting:
            waiter = self._waiting.pop(0)
            if not waiter.done():
                waiter.set_result((event, False))
        else:
            self._queue.append(event)

    def end(self, result: R | None = None) -> None:
        """End the stream."""
        self._done = True
        if result is not None and not self._final_result_future.done():
            self._final_result_future.set_result(result)

        # Notify all waiting consumers that we're done
        while self._waiting:
            waiter = self._waiting.pop(0)
            if not waiter.done():
                waiter.set_result((None, True))

    async def __aiter__(self) -> AsyncIterator[T]:
        """Async iterator implementation."""
        while True:
            if self._queue:
                yield self._queue.pop(0)
            elif self._done:
                return
            else:
                loop = asyncio.get_event_loop()
                future: asyncio.Future[tuple[T | None, bool]] = loop.create_future()
                self._waiting.append(future)
                value, done = await future
                if done:
                    return
                if value is not None:
                    yield value

    async def result(self) -> R:
        """Await the final result."""
        return await self._final_result_future


class AssistantMessageEventStream(EventStream[AssistantMessageEvent, AssistantMessage]):
    """Event stream for assistant message events."""

    def __init__(self) -> None:
        super().__init__(
            is_complete=lambda event: event.type in ("done", "error"),
            extract_result=lambda event: (
                event.message if event.type == "done" else event.error if event.type == "error" else None
            ),
        )

    def _extract_result_impl(self, event: AssistantMessageEvent) -> AssistantMessage:
        """Extract the final result from an event."""
        if event.type == "done":
            return event.message
        elif event.type == "error":
            return event.error
        raise ValueError("Unexpected event type for final result")


def create_assistant_message_event_stream() -> AssistantMessageEventStream:
    """Factory function for AssistantMessageEventStream."""
    return AssistantMessageEventStream()
