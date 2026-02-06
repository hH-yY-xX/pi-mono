"""
Example usage of the pi-coding-agent session management and compaction
"""
from pi_coding_agent import SessionManager, CompactionManager, CompactionSettings
from pi_coding_agent.models import (
    UserMessage, AssistantMessage, Usage, ThinkingLevel, MessageType
)
import json


def example_usage():
    """Demonstrate basic usage of session management and compaction."""
    
    # Create a new session
    session = SessionManager.create("/path/to/project")
    
    # Add some messages
    user_msg = UserMessage(
        content="Hello, I need help with my Python project"
    )
    session.append_message(user_msg)
    
    # Simulate assistant response
    assistant_msg = AssistantMessage(
        content=[{"type": "text", "text": "I'd be happy to help with your Python project!"}],
        api="openai",
        provider="openai",
        model="gpt-4",
        usage=Usage(input=100, output=50, total_tokens=150),
        stop_reason="stop"
    )
    session.append_message(assistant_msg)
    
    # Change thinking level
    session.append_thinking_level_change(ThinkingLevel.HIGH)
    
    # Change model
    session.append_model_change("anthropic", "claude-3-opus")
    
    # Check if compaction is needed
    context_tokens = 150  # Simulated token count
    context_window = 128000  # Typical context window
    
    settings = CompactionSettings()
    if CompactionManager.should_compact(context_tokens, context_window, settings):
        print("Compaction would be triggered")
    
    # Prepare for compaction
    entries = session.get_entries()
    preparation = CompactionManager.prepare_compaction(entries, settings)
    
    if preparation:
        print(f"Would compact {len(preparation.messages_to_summarize)} messages")
        print(f"Keeping {len(preparation.turn_prefix_messages)} turn prefix messages")
        print(f"Split turn: {preparation.is_split_turn}")
    
    # Get session context
    context = session.build_session_context()
    print(f"Context has {len(context.messages)} messages")
    print(f"Thinking level: {context.thinking_level}")
    print(f"Model: {context.model}")
    
    # Demonstrate branching
    leaf_id = session.get_leaf_id()
    if leaf_id:
        # Create a branch with summary
        session.branch_with_summary(
            leaf_id, 
            "User asked for help with Python project"
        )
        print("Created branch with summary")
    
    return session


if __name__ == "__main__":
    session = example_usage()
    print(f"Session ID: {getattr(session, 'session_id', 'N/A')}")
    print(f"Session file: {getattr(session, 'session_file', 'In-memory')}")