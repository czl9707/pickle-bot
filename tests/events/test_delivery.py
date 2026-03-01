# tests/events/test_delivery.py
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from picklebot.core.events import OutboundEvent, Source
from picklebot.core.eventbus import EventBus
from picklebot.server.delivery_worker import chunk_message, DeliveryWorker


@pytest.fixture
def mock_context(tmp_path):
    context = MagicMock()
    context.config = MagicMock()
    context.config.messagebus = MagicMock()
    context.config.messagebus.telegram = None
    context.config.messagebus.discord = None
    context.config.messagebus.default_platform = None
    context.config.event_path = tmp_path / ".events"
    context.eventbus = EventBus(context)
    # Mock platform buses list
    context.messagebus_buses = []
    return context


@pytest.mark.asyncio
async def test_delivery_worker_creation(mock_context):
    worker = DeliveryWorker(mock_context)
    assert worker.context == mock_context


@pytest.mark.asyncio
async def test_delivery_worker_handles_outbound_event(mock_context):
    worker = DeliveryWorker(mock_context)

    # Mock the lookup
    worker._lookup_platform = MagicMock(
        return_value={
            "platform": "telegram",
            "user_id": "user123",
            "chat_id": "123456",
        }
    )

    # Create mock telegram bus
    mock_telegram_bus = MagicMock()
    mock_telegram_bus.platform_name = "telegram"
    mock_telegram_bus.reply = AsyncMock()
    mock_context.messagebus_buses = [mock_telegram_bus]

    event = OutboundEvent(
        session_id="test-session",
        agent_id="pickle",
        source=Source.agent("pickle"),
        content="Hello",
        timestamp=12345.0,
    )

    # Patch at the module where TelegramContext is defined
    with patch("picklebot.messagebus.telegram_bus.TelegramContext") as MockContext:
        mock_ctx_instance = MagicMock()
        MockContext.return_value = mock_ctx_instance

        await worker.handle_event(event)

        # Should have called telegram bus reply with content and context
        mock_telegram_bus.reply.assert_called_once_with("Hello", mock_ctx_instance)
        MockContext.assert_called_once_with(user_id="user123", chat_id="123456")


@pytest.mark.asyncio
async def test_delivery_worker_handles_cli_platform(mock_context, capsys):
    worker = DeliveryWorker(mock_context)

    # Mock the lookup for CLI
    worker._lookup_platform = MagicMock(
        return_value={
            "platform": "cli",
        }
    )

    event = OutboundEvent(
        session_id="test-session",
        agent_id="pickle",
        source=Source.agent("pickle"),
        content="Hello CLI",
        timestamp=12345.0,
    )

    await worker.handle_event(event)

    # Should print to stdout
    captured = capsys.readouterr()
    assert "Hello CLI" in captured.out


def test_chunk_message_under_limit():
    result = chunk_message("Hello world", limit=100)
    assert result == ["Hello world"]


def test_chunk_message_exact_limit():
    message = "x" * 100
    result = chunk_message(message, limit=100)
    assert result == [message]


def test_chunk_message_splits_at_paragraph():
    message = "Para one\n\nPara two\n\nPara three"
    result = chunk_message(message, limit=15)
    # "Para one" = 8 chars
    # "Para two" = 8 chars
    # "Para three" = 10 chars
    assert len(result) == 3
    assert "Para one" in result[0]
    assert "Para two" in result[1]


def test_chunk_message_hard_split():
    message = "A" * 50  # Single long "paragraph"
    result = chunk_message(message, limit=20)
    assert len(result) == 3
    assert len(result[0]) == 20
    assert len(result[1]) == 20
    assert len(result[2]) == 10


def test_chunk_message_mixed():
    message = "Short\n\n" + "B" * 50 + "\n\nEnd"
    result = chunk_message(message, limit=20)
    # "Short" = 5 chars - chunk 1
    # 50 B's - chunks 2,3,4 (20+20+10)
    # "End" = 3 chars - chunk 5
    assert len(result) >= 3


def test_platform_limits():
    from picklebot.server.delivery_worker import PLATFORM_LIMITS

    assert PLATFORM_LIMITS["telegram"] == 4096
    assert PLATFORM_LIMITS["discord"] == 2000
    assert PLATFORM_LIMITS["cli"] == float("inf")


def test_lookup_platform_default_platform(mock_context):
    """Should use default_platform when session not found."""
    # Configure discord as default
    mock_context.config.messagebus.discord = MagicMock()
    mock_context.config.messagebus.discord.default_chat_id = "channel-456"
    mock_context.config.messagebus.default_platform = "discord"

    worker = DeliveryWorker(mock_context)

    # Test default platform routing for unknown session
    result = worker._lookup_platform("some-session-id")

    assert result["platform"] == "discord"
    assert result["channel_id"] == "channel-456"


def test_lookup_platform_fallback_to_cli(mock_context):
    """Should fallback to CLI when no default platform configured."""
    worker = DeliveryWorker(mock_context)

    # No default platform configured
    result = worker._lookup_platform("some-session-id")

    assert result["platform"] == "cli"


@pytest.mark.asyncio
async def test_delivery_worker_handles_proactive_event(mock_context):
    """Should deliver proactive messages via post() instead of reply()."""
    worker = DeliveryWorker(mock_context)

    # Configure telegram as default platform
    mock_context.config.messagebus.telegram = MagicMock()
    mock_context.config.messagebus.telegram.default_chat_id = "chat-123"
    mock_context.config.messagebus.default_platform = "telegram"

    # Create mock telegram bus
    mock_telegram_bus = MagicMock()
    mock_telegram_bus.platform_name = "telegram"
    mock_telegram_bus.post = AsyncMock()
    mock_context.messagebus_buses = [mock_telegram_bus]

    # Create OutboundEvent - session not in mapping, uses default_platform
    event = OutboundEvent(
        session_id="test-uuid-1234",
        agent_id="pickle",
        source=Source.agent("pickle"),
        content="Proactive message",
        timestamp=12345.0,
    )

    await worker.handle_event(event)

    # Should have called telegram bus post (not reply) for proactive message
    mock_telegram_bus.post.assert_called_once_with("Proactive message")
