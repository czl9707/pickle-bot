"""Tests for MessageBus abstract interface."""

import pytest
from picklebot.messagebus.base import MessageBus


class MockBus(MessageBus):
    """Mock implementation for testing."""

    @property
    def platform_name(self) -> str:
        return "mock"

    async def start(self, on_message) -> None:
        pass

    async def send_message(self, user_id: str, content: str) -> None:
        pass

    async def stop(self) -> None:
        pass


def test_messagebus_has_platform_name():
    """Test that MessageBus has platform_name property."""
    bus = MockBus()
    assert bus.platform_name == "mock"


@pytest.mark.anyio
async def test_messagebus_send_message_interface():
    """Test that send_message can be called."""
    bus = MockBus()
    await bus.send_message("user123", "test message")
    # Should not raise
