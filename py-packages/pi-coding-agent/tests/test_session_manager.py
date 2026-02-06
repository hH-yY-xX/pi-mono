# Test session management functionality
import pytest
from pi_coding_agent.session_manager import SessionManager
from pi_coding_agent.models import UserMessage, AssistantMessage, Usage, ThinkingLevel


class TestSessionManager:
    def test_create_session(self):
        """Test creating a new session."""
        session = SessionManager.create("/test/project")
        assert session.cwd == "/test/project"
        assert session.get_header() is not None
        assert session.get_header().version == 3
    
    def test_append_message(self):
        """Test appending messages to session."""
        session = SessionManager.in_memory("/test")
        
        user_msg = UserMessage(content="Hello world")
        msg_id = session.append_message(user_msg)
        
        assert msg_id is not None
        assert len(session.get_entries()) == 1
        
        entry = session.get_entry(msg_id)
        assert entry is not None
        assert entry.message.content == "Hello world"
    
    def test_thinking_level_change(self):
        """Test changing thinking level."""
        session = SessionManager.in_memory("/test")
        
        level_id = session.append_thinking_level_change(ThinkingLevel.HIGH)
        assert level_id is not None
        
        entry = session.get_entry(level_id)
        assert entry.thinking_level == ThinkingLevel.HIGH
    
    def test_model_change(self):
        """Test changing model."""
        session = SessionManager.in_memory("/test")
        
        model_id = session.append_model_change("openai", "gpt-4")
        assert model_id is not None
        
        entry = session.get_entry(model_id)
        assert entry.provider == "openai"
        assert entry.model_id == "gpt-4"
    
    def test_session_context(self):
        """Test building session context."""
        session = SessionManager.in_memory("/test")
        
        # Add messages
        user_msg = UserMessage(content="Test message")
        session.append_message(user_msg)
        
        assistant_msg = AssistantMessage(
            content=[{"type": "text", "text": "Response"}],
            api="test",
            provider="test",
            model="test-model",
            usage=Usage(),
            stop_reason="stop"
        )
        session.append_message(assistant_msg)
        
        # Build context
        context = session.build_session_context()
        assert len(context.messages) == 2
        assert context.thinking_level == ThinkingLevel.OFF
        assert context.model == {"provider": "test", "model_id": "test-model"}
    
    def test_branching(self):
        """Test session branching functionality."""
        session = SessionManager.in_memory("/test")
        
        # Add messages
        msg1_id = session.append_message(UserMessage(content="Message 1"))
        msg2_id = session.append_message(UserMessage(content="Message 2"))
        
        # Branch to first message
        session.branch(msg1_id)
        assert session.get_leaf_id() == msg1_id
        
        # Add message to new branch
        msg3_id = session.append_message(UserMessage(content="Message 3"))
        assert session.get_leaf_id() == msg3_id
        
        # Verify branch structure
        branch = session.get_branch()
        assert len(branch) == 3  # header + msg1 + msg3
        assert branch[-1].id == msg3_id


class TestCompaction:
    def test_token_estimation(self):
        """Test token estimation for different message types."""
        from pi_coding_agent.compaction import CompactionManager
        
        # Test user message
        user_msg = UserMessage(content="Hello world")
        tokens = CompactionManager.estimate_tokens(user_msg)
        assert tokens > 0
        
        # Test assistant message
        assistant_msg = AssistantMessage(
            content=[{"type": "text", "text": "Response"}],
            api="test",
            provider="test",
            model="test-model",
            usage=Usage(),
            stop_reason="stop"
        )
        tokens = CompactionManager.estimate_tokens(assistant_msg)
        assert tokens > 0
    
    def test_should_compact(self):
        """Test compaction trigger logic."""
        from pi_coding_agent.compaction import CompactionManager, CompactionSettings
        
        settings = CompactionSettings(reserve_tokens=1000, keep_recent_tokens=2000)
        
        # Should not compact - within limits
        assert not CompactionManager.should_compact(500, 10000, settings)
        
        # Should compact - exceeding limits
        assert CompactionManager.should_compact(9500, 10000, settings)
        
        # Should not compact - disabled
        disabled_settings = CompactionSettings(enabled=False)
        assert not CompactionManager.should_compact(9500, 10000, disabled_settings)


if __name__ == "__main__":
    pytest.main([__file__])