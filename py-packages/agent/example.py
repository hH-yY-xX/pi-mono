"""
Example usage of the pi-agent-core package.
"""

import asyncio
import time
from pi_agent_core import (
    Agent,
    AgentOptions,
    AgentTool,
    AgentToolResult,
    TextContent,
    UserMessage,
)

# Example tool implementation
class GetCurrentTimeTool(AgentTool):
    def __init__(self):
        super().__init__()
        self.name = "get_current_time"
        self.label = "Get Current Time"
        self.description = "Get the current time"
        self.parameters = {}

    async def execute(self, tool_call_id, params, signal, on_update):
        """Execute the get current time tool."""
        current_time = time.strftime("%Y-%m-%d %H:%M:%S")
        
        # Optional: stream progress update
        if on_update:
            on_update(AgentToolResult(
                content=[TextContent(text="Getting current time...")],
                details={}
            ))
        
        return AgentToolResult(
            content=[TextContent(text=f"The current time is: {current_time}")],
            details={"timestamp": current_time}
        )

async def main():
    """Main example function."""
    # Create agent with basic configuration
    agent = Agent(AgentOptions(
        initial_state={
            "system_prompt": "You are a helpful assistant that can tell the time.",
        }
    ))
    
    # Add tools
    agent.set_tools([GetCurrentTimeTool()])
    
    # Subscribe to events
    def on_event(event):
        if hasattr(event, 'type'):
            print(f"Event: {event.type}")
            if event.type == "message_update":
                if hasattr(event, 'assistant_message_event'):
                    if hasattr(event.assistant_message_event, 'type'):
                        if event.assistant_message_event.type == "text_delta":
                            print(event.assistant_message_event.delta, end="", flush=True)
    
    agent.subscribe(on_event)
    
    # Send a prompt
    print("Sending prompt...")
    try:
        await agent.prompt("What time is it?")
        print("\nPrompt completed!")
    except Exception as e:
        print(f"Error: {e}")
    
    # Wait a bit to see the final state
    await asyncio.sleep(1)
    
    # Print final messages
    print("\nFinal messages:")
    for i, msg in enumerate(agent.state.messages):
        print(f"  {i}: {msg.role} - {getattr(msg, 'content', [])}")

if __name__ == "__main__":
    asyncio.run(main())