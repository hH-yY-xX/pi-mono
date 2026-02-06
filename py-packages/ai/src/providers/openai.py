"""
OpenAI API provider implementation.
"""

import asyncio
from typing import Optional
from ..types import (
    Model,
    Context,
    StreamOptions,
    SimpleStreamOptions,
    TextContent,
    Usage
)
from ..utils.event_stream import create_assistant_message_event_stream, AssistantMessageEventStream
from ..api_registry import ApiProvider, register_api_provider

class OpenAIProvider(ApiProvider):
    """OpenAI API provider implementation."""
    
    def stream(
        self,
        model: Model,
        context: Context,
        options: Optional[StreamOptions] = None,
    ) -> AssistantMessageEventStream:
        """Stream completion using OpenAI API."""
        stream = create_assistant_message_event_stream()
        
        async def run():
            try:
                # Initialize the message
                output = AssistantMessage(
                    role="assistant",
                    content=[],
                    api=model.api,
                    provider=model.provider,
                    model=model.id,
                    usage=Usage(),
                    stop_reason="stop",
                    timestamp=int(asyncio.get_event_loop().time() * 1000)
                )
                
                # Start event
                stream.push({"type": "start", "partial": output})
                
                # Simulate streaming response
                content_index = 0
                text_content = TextContent(text="")
                output.content.append(text_content)
                
                # Text content start
                stream.push({
                    "type": "text_start",
                    "content_index": content_index,
                    "partial": output
                })
                
                # Simulate streaming text chunks
                text_chunks = ["This is a response", " from OpenAI", " API."]
                for chunk in text_chunks:
                    text_content.text += chunk
                    stream.push({
                        "type": "text_delta",
                        "content_index": content_index,
                        "delta": chunk,
                        "partial": output
                    })
                    await asyncio.sleep(0.1)
                
                # Text content end
                stream.push({
                    "type": "text_end",
                    "content_index": content_index,
                    "content": text_content.text,
                    "partial": output
                })
                
                # Done event
                stream.push({
                    "type": "done",
                    "reason": "stop",
                    "message": output
                })
                
                stream.end(output)
                
            except Exception as e:
                error_msg = AssistantMessage(
                    role="assistant",
                    content=[],
                    api=model.api,
                    provider=model.provider,
                    model=model.id,
                    usage=Usage(),
                    stop_reason="error",
                    error_message=str(e),
                    timestamp=int(asyncio.get_event_loop().time() * 1000)
                )
                stream.push({
                    "type": "error",
                    "reason": "error",
                    "error": error_msg
                })
                stream.end(error_msg)
        
        # Start the async task
        asyncio.create_task(run())
        return stream
    
    def stream_simple(
        self,
        model: Model,
        context: Context,
        options: Optional[SimpleStreamOptions] = None,
    ) -> AssistantMessageEventStream:
        """Stream completion with simplified options."""
        return self.stream(model, context, options)

# Register the providers
register_api_provider("openai-completions", OpenAIProvider())
register_api_provider("openai-responses", OpenAIProvider())