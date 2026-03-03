import pytest
from unittest.mock import Mock, AsyncMock, patch
from picklebot.server.delivery_worker import (
    DeliveryWorker,
    chunk_message,
    PLATFORM_LIMITS,
)
from picklebot.core.events import OutboundEvent


def test_delivery_worker_has_lru_cache(mock_context):
    """DeliveryWorker should use LRU cache for session lookup."""
    worker = DeliveryWorker(mock_context)

    # Check that _get_session_source is decorated with lru_cache
    assert hasattr(worker._get_session_source, "cache_info")


def test_get_session_source_returns_session(mock_context):
    """_get_session_source should return session with source."""
    from picklebot.core.history import HistorySession

    mock_session = HistorySession(
        id="session-123",
        agent_id="pickle",
        source="platform-telegram:123456:123456",
        created_at="2026-03-01T10:00:00",
        updated_at="2026-03-01T10:00:00",
    )
    mock_context.history_store.list_sessions.return_value = [mock_session]

    worker = DeliveryWorker(mock_context)
    result = worker._get_session_source("session-123")

    assert result == mock_session
    assert result.source == "platform-telegram:123456:123456"


def test_get_session_source_returns_none_if_not_found(mock_context):
    """_get_session_source should return None if session not found."""
    mock_context.history_store.list_sessions.return_value = []

    worker = DeliveryWorker(mock_context)
    result = worker._get_session_source("unknown-session")

    assert result is None


@pytest.mark.asyncio
async def test_handle_event_skips_if_no_source(mock_context):
    """handle_event should skip delivery if session has no source."""
    mock_context.history_store.list_sessions.return_value = []

    worker = DeliveryWorker(mock_context)
    event = OutboundEvent(
        session_id="unknown",
        agent_id="pickle",
        source="agent:pickle",
        content="Hello",
    )

    # Spy on the ack method
    with patch.object(mock_context.eventbus, "ack") as mock_ack:
        await worker.handle_event(event)
        # Should not ack since we skipped
        mock_ack.assert_not_called()


@pytest.mark.asyncio
async def test_handle_event_delivers_to_platform(mock_context):
    """handle_event should deliver to platform from session source."""
    from picklebot.core.history import HistorySession

    mock_session = HistorySession(
        id="session-123",
        agent_id="pickle",
        source="platform-telegram:123456:123456",
        created_at="2026-03-01T10:00:00",
        updated_at="2026-03-01T10:00:00",
    )
    mock_context.history_store.list_sessions.return_value = [mock_session]

    mock_bus = Mock()
    mock_bus.platform_name = "telegram"
    mock_bus.reply = AsyncMock()
    mock_context.messagebus_buses = [mock_bus]

    worker = DeliveryWorker(mock_context)
    event = OutboundEvent(
        session_id="session-123",
        agent_id="pickle",
        source="agent:pickle",
        content="Hello",
    )

    # Spy on the ack method
    with patch.object(mock_context.eventbus, "ack") as mock_ack:
        await worker.handle_event(event)

        mock_bus.reply.assert_called_once()
        mock_ack.assert_called_once_with(event)


@pytest.mark.asyncio
async def test_delivery_worker_handles_cli_platform(mock_context):
    """handle_event should deliver to CLI platform correctly."""
    from picklebot.core.history import HistorySession

    mock_session = HistorySession(
        id="test-session",
        agent_id="pickle",
        source="platform-cli:cli-user",
        created_at="2026-03-01T10:00:00",
        updated_at="2026-03-01T10:00:00",
    )
    mock_context.history_store.list_sessions.return_value = [mock_session]

    # Create mock CLI bus
    mock_cli_bus = Mock()
    mock_cli_bus.platform_name = "cli"
    mock_cli_bus.reply = AsyncMock()
    mock_context.messagebus_buses = [mock_cli_bus]

    worker = DeliveryWorker(mock_context)
    event = OutboundEvent(
        session_id="test-session",
        agent_id="pickle",
        source="agent:pickle",
        content="Hello CLI",
    )

    await worker.handle_event(event)

    # Should have called CLI bus reply
    mock_cli_bus.reply.assert_called_once()


# chunk_message unit tests


def test_chunk_message_under_limit():
    """Messages under limit should not be split."""
    result = chunk_message("Hello world", limit=100)
    assert result == ["Hello world"]


def test_chunk_message_exact_limit():
    """Messages exactly at limit should not be split."""
    message = "x" * 100
    result = chunk_message(message, limit=100)
    assert result == [message]


def test_chunk_message_splits_at_paragraph():
    """Long messages should split at paragraph boundaries when possible."""
    message = "Para one\n\nPara two\n\nPara three"
    result = chunk_message(message, limit=15)
    # "Para one" = 8 chars
    # "Para two" = 8 chars
    # "Para three" = 10 chars
    assert len(result) == 3
    assert "Para one" in result[0]
    assert "Para two" in result[1]


def test_chunk_message_hard_split():
    """Messages without paragraph breaks should be hard-split."""
    message = "A" * 50  # Single long "paragraph"
    result = chunk_message(message, limit=20)
    assert len(result) == 3
    assert len(result[0]) == 20
    assert len(result[1]) == 20
    assert len(result[2]) == 10


def test_chunk_message_mixed():
    """Messages with mixed content should split appropriately."""
    message = "Short\n\n" + "B" * 50 + "\n\nEnd"
    result = chunk_message(message, limit=20)
    # "Short" = 5 chars - chunk 1
    # 50 B's - chunks 2,3,4 (20+20+10)
    # "End" = 3 chars - chunk 5
    assert len(result) >= 3


def test_platform_limits():
    """Platform limits should match expected values."""
    assert PLATFORM_LIMITS["telegram"] == 4096
    assert PLATFORM_LIMITS["discord"] == 2000
    assert PLATFORM_LIMITS["cli"] == float("inf")


class TestDefaultDeliverySource:
    """Tests for default_delivery_source fallback in delivery."""

    @pytest.mark.asyncio
    async def test_uses_default_when_no_platform(self, mock_context):
        """Should deliver to default_delivery_source when session has no platform."""
        from picklebot.core.history import HistorySession

        # Session with non-platform source
        mock_session = HistorySession(
            id="session-123",
            agent_id="pickle",
            source="agent:pickle",
            created_at="2026-03-01T10:00:00",
            updated_at="2026-03-01T10:00:00",
        )
        mock_context.history_store.list_sessions.return_value = [mock_session]

        # Set default delivery source
        mock_context.config.default_delivery_source = "platform-telegram:123:456"

        # Mock telegram bus
        mock_bus = Mock()
        mock_bus.platform_name = "telegram"
        mock_bus.reply = AsyncMock()
        mock_context.messagebus_buses = [mock_bus]

        worker = DeliveryWorker(mock_context)
        event = OutboundEvent(
            session_id="session-123",
            agent_id="pickle",
            source="agent:pickle",
            content="Hello",
        )

        with patch.object(mock_context.eventbus, "ack") as mock_ack:
            await worker.handle_event(event)

        mock_bus.reply.assert_called_once()
        mock_ack.assert_called_once_with(event)

    @pytest.mark.asyncio
    async def test_skips_when_no_default_configured(self, mock_context):
        """Should skip with warning when no default_delivery_source configured."""
        from picklebot.core.history import HistorySession

        # Session with non-platform source
        mock_session = HistorySession(
            id="session-123",
            agent_id="pickle",
            source="agent:pickle",
            created_at="2026-03-01T10:00:00",
            updated_at="2026-03-01T10:00:00",
        )
        mock_context.history_store.list_sessions.return_value = [mock_session]
        mock_context.config.default_delivery_source = None

        worker = DeliveryWorker(mock_context)
        event = OutboundEvent(
            session_id="session-123",
            agent_id="pickle",
            source="agent:pickle",
            content="Hello",
        )

        with patch.object(mock_context.eventbus, "ack") as mock_ack:
            await worker.handle_event(event)

        mock_ack.assert_not_called()

    @pytest.mark.asyncio
    async def test_platform_source_unchanged(self, mock_context):
        """Platform sources should still deliver directly (existing behavior)."""
        from picklebot.core.history import HistorySession

        # Session with platform source
        mock_session = HistorySession(
            id="session-123",
            agent_id="pickle",
            source="platform-telegram:999:888",
            created_at="2026-03-01T10:00:00",
            updated_at="2026-03-01T10:00:00",
        )
        mock_context.history_store.list_sessions.return_value = [mock_session]

        # Set a different default (should be ignored)
        mock_context.config.default_delivery_source = "platform-discord:111:222"

        # Mock telegram bus only
        mock_bus = Mock()
        mock_bus.platform_name = "telegram"
        mock_bus.reply = AsyncMock()
        mock_context.messagebus_buses = [mock_bus]

        worker = DeliveryWorker(mock_context)
        event = OutboundEvent(
            session_id="session-123",
            agent_id="pickle",
            source="agent:pickle",
            content="Hello",
        )

        with patch.object(mock_context.eventbus, "ack") as mock_ack:
            await worker.handle_event(event)

        # Should deliver to telegram (from session source), not discord (default)
        mock_bus.reply.assert_called_once()
        mock_ack.assert_called_once_with(event)

    @pytest.mark.asyncio
    async def test_invalid_default_logs_error(self, mock_context):
        """Should log error and skip if default_delivery_source is invalid."""
        from picklebot.core.history import HistorySession

        # Session with non-platform source
        mock_session = HistorySession(
            id="session-123",
            agent_id="pickle",
            source="agent:pickle",
            created_at="2026-03-01T10:00:00",
            updated_at="2026-03-01T10:00:00",
        )
        mock_context.history_store.list_sessions.return_value = [mock_session]

        # Invalid default source string
        mock_context.config.default_delivery_source = "invalid:source:format"

        worker = DeliveryWorker(mock_context)
        event = OutboundEvent(
            session_id="session-123",
            agent_id="pickle",
            source="agent:pickle",
            content="Hello",
        )

        with patch.object(mock_context.eventbus, "ack") as mock_ack:
            await worker.handle_event(event)

        # Should skip without acking
        mock_ack.assert_not_called()

    @pytest.mark.asyncio
    async def test_non_platform_default_logs_error(self, mock_context):
        """Should log error when default_delivery_source is a non-platform source."""
        from picklebot.core.history import HistorySession

        mock_session = HistorySession(
            id="session-123",
            agent_id="pickle",
            source="agent:pickle",
            created_at="2026-03-01T10:00:00",
            updated_at="2026-03-01T10:00:00",
        )
        mock_context.history_store.list_sessions.return_value = [mock_session]
        # Valid but non-platform source
        mock_context.config.default_delivery_source = "agent:pickle"

        worker = DeliveryWorker(mock_context)
        event = OutboundEvent(
            session_id="session-123",
            agent_id="pickle",
            source="agent:pickle",
            content="Hello",
        )

        with patch.object(mock_context.eventbus, "ack") as mock_ack:
            await worker.handle_event(event)

        # Should skip without acking
        mock_ack.assert_not_called()
