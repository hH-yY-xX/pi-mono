"""
Event stream implementation for asynchronous message streaming.
"""

import asyncio
from typing import (
    AsyncIterator,
    Awaitable,
    Callable,
    Generic,
    Optional,
    TypeVar,
    Union
)
from .types import AssistantMessage, AssistantMessageEvent

T = TypeVar('T')
R = TypeVar('R')

class EventStream(Generic[T, R]):
    """
    Generic event stream class for async iteration.
    """
    
    def __init__(
        self,
        is_complete: Callable[[T], bool],
        extract_result: Callable[[T], R]
    ):
        self._queue: list[T] = []
        self._waiting: list[asyncio.Future] = []
        self._done = False
        self._is_complete = is_complete
        self._extract_result = extract_result
        self._final_result_promise: asyncio.Future[R] = asyncio.Future()
        
    def push(self, event: T) -> None:
        """Push an event to the stream."""
        if self._done:
            return
            
        if self._is_complete(event):
            self._done = True
            try:
                result = self._extract_result(event)
                if not self._final_result_promise.done():
                    self._final_result_promise.set_result(result)
            except Exception as e:
                if not self._final_result_promise.done():
                    self._final_result_promise.set_exception(e)
        
        # Deliver to waiting consumer or queue it
        if self._waiting:
            waiter = self._waiting.pop(0)
            waiter.set_result(event)
        else:
            self._queue.append(event)
            
    def end(self, result: Optional[R] = None) -> None:
        """End the stream with an optional result."""
        self._done = True
        if result is not None and not self._final_result_promise.done():
            self._final_result_promise.set_result(result)
            
        # Notify all waiting consumers that we're done
        while self._waiting:
            waiter = self._waiting.pop(0)
            waiter.set_exception(StopAsyncIteration())
            
    def __aiter__(self) -> AsyncIterator[T]:
        return self
        
    async def __anext__(self) -> T:
        if self._queue:
            return self._queue.pop(0)
        elif self._done:
            raise StopAsyncIteration()
        else:
            future: asyncio.Future = asyncio.Future()
            self._waiting.append(future)
            try:
                return await future
            except asyncio.CancelledError:
                self._waiting.remove(future)
                raise
                
    async def result(self) -> R:
        """Get the final result of the stream."""
        return await self._final_result_promise

class AssistantMessageEventStream(EventStream[AssistantMessageEvent, AssistantMessage]):
    """
    Specialized event stream for assistant message events.
    """
    
    def __init__(self):
        def is_complete(event: AssistantMessageEvent) -> bool:
            return event.type in ("done", "error")
            
        def extract_result(event: AssistantMessageEvent) -> AssistantMessage:
            if event.type == "done":
                return event.message
            elif event.type == "error":
                return event.error
            else:
                raise ValueError("Unexpected event type for final result")
                
        super().__init__(is_complete, extract_result)

def create_assistant_message_event_stream() -> AssistantMessageEventStream:
    """Factory function for AssistantMessageEventStream."""
    return AssistantMessageEventStream()