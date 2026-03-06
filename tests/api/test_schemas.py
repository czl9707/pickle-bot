"""Tests for WebSocket message schemas."""

import pytest
from pydantic import ValidationError
from picklebot.api.schemas import WebSocketMessage


class TestWebSocketMessage:
    """Test WebSocketMessage validation."""

    def test_valid_message_with_all_fields(self):
        """Test valid message with all fields."""
        msg = WebSocketMessage(
            source="user-123", content="Hello Pickle!", agent_id="pickle"
        )
        assert msg.source == "user-123"
        assert msg.content == "Hello Pickle!"
        assert msg.agent_id == "pickle"

    def test_valid_message_without_agent_id(self):
        """Test valid message without optional agent_id."""
        msg = WebSocketMessage(source="user-456", content="Hello!")
        assert msg.source == "user-456"
        assert msg.content == "Hello!"
        assert msg.agent_id is None

    def test_invalid_message_missing_source(self):
        """Test invalid message without required source."""
        with pytest.raises(ValidationError) as exc_info:
            WebSocketMessage(content="Hello!")

        assert "source" in str(exc_info.value)

    def test_invalid_message_missing_content(self):
        """Test invalid message without required content."""
        with pytest.raises(ValidationError) as exc_info:
            WebSocketMessage(source="user-123")

        assert "content" in str(exc_info.value)

    def test_invalid_message_empty_source(self):
        """Test invalid message with empty source string."""
        with pytest.raises(ValidationError) as exc_info:
            WebSocketMessage(source="", content="Hello!")

        assert "at least 1 character" in str(exc_info.value).lower()

    def test_invalid_message_empty_content(self):
        """Test invalid message with empty content string."""
        with pytest.raises(ValidationError) as exc_info:
            WebSocketMessage(source="user-123", content="")

        assert "at least 1 character" in str(exc_info.value).lower()
