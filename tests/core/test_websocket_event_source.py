"""Tests for WebSocketEventSource."""

import pytest
from picklebot.core.events import WebSocketEventSource


class TestWebSocketEventSource:
    """Parametrized tests for WebSocketEventSource."""

    @pytest.mark.parametrize("user_id,expected_str,type_props", [
        (
            "user-123",
            "platform-ws:user-123",
            {"is_platform": True, "is_agent": False, "is_cron": False},
        ),
        (
            "user:with:colons",
            "platform-ws:user:with:colons",
            {"is_platform": True, "is_agent": False, "is_cron": False},
        ),
    ])
    def test_source_roundtrip(self, user_id, expected_str, type_props):
        """Source should serialize/deserialize and have correct type properties."""
        # Create
        source = WebSocketEventSource(user_id=user_id)

        # Check serialization
        assert str(source) == expected_str

        # Check roundtrip
        restored = WebSocketEventSource.from_string(expected_str)
        assert restored.user_id == user_id

        # Check type properties
        for prop, expected in type_props.items():
            assert getattr(source, prop) == expected

    @pytest.mark.parametrize("invalid_str,error_match", [
        ("invalid-namespace:user", "Invalid WebSocketEventSource"),
        ("invalid-format", "Invalid WebSocketEventSource"),
        ("platform-ws:", "Invalid WebSocketEventSource"),
    ])
    def test_from_string_rejects_invalid(self, invalid_str, error_match):
        """from_string should reject invalid formats."""
        with pytest.raises(ValueError, match=error_match):
            WebSocketEventSource.from_string(invalid_str)
