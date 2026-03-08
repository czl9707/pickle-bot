# tests/core/test_routing.py

import pytest
from unittest.mock import patch

from picklebot.core.routing import Binding, RoutingTable


def test_binding_compiles_pattern():
    """Binding should compile value into regex pattern."""
    binding = Binding(agent="pickle", value="telegram:123456")

    assert binding.pattern.match("telegram:123456")
    assert not binding.pattern.match("telegram:789")


def test_binding_tier_literal():
    """Literal strings should be tier 0 (most specific)."""
    binding = Binding(agent="pickle", value="telegram:123456")

    assert binding.tier == 0


def test_binding_tier_specific_regex():
    """Specific regex patterns should be tier 1."""
    binding = Binding(agent="pickle", value="telegram:[0-9]+")

    assert binding.tier == 1


def test_binding_tier_wildcard():
    """Wildcard patterns (.*) should be tier 2 (least specific)."""
    binding = Binding(agent="pickle", value="telegram:.*")

    assert binding.tier == 2


def test_binding_tier_catch_all():
    """Catch-all pattern should be tier 2."""
    binding = Binding(agent="pickle", value=".*")

    assert binding.tier == 2


def test_binding_matches_full_string():
    """Pattern should match full string (anchored)."""
    binding = Binding(agent="pickle", value="telegram:123")

    assert binding.pattern.match("telegram:123")
    assert not binding.pattern.match("telegram:123456")  # extra chars


# RoutingTable tests


class MockConfig:
    def __init__(self, bindings, default_agent="pickle"):
        self.routing = {"bindings": bindings}
        self.default_agent = default_agent


class MockContext:
    def __init__(self, bindings, default_agent="pickle"):
        self.config = MockConfig(bindings, default_agent=default_agent)


def test_routing_table_resolve_exact_match():
    """RoutingTable should resolve exact matches."""
    context = MockContext(
        [
            {"agent": "cookie", "value": "telegram:123456"},
            {"agent": "pickle", "value": "telegram:.*"},
        ]
    )
    table = RoutingTable(context)

    assert table.resolve("telegram:123456") == "cookie"


def test_routing_table_resolve_wildcard():
    """RoutingTable should fall back to wildcard patterns."""
    context = MockContext(
        [
            {"agent": "cookie", "value": "telegram:123456"},
            {"agent": "pickle", "value": "telegram:.*"},
        ]
    )
    table = RoutingTable(context)

    assert table.resolve("telegram:789") == "pickle"


def test_routing_table_resolve_no_match():
    """RoutingTable should return default_agent if no pattern matches."""
    context = MockContext(
        [
            {"agent": "pickle", "value": "telegram:.*"},
        ]
    )
    table = RoutingTable(context)

    assert table.resolve("discord:123") == "pickle"


def test_routing_table_resolve_fallback_to_default():
    """RoutingTable should return default_agent if no pattern matches."""
    context = MockContext(
        [
            {"agent": "pickle", "value": "telegram:.*"},
        ],
        default_agent="cookie",
    )
    table = RoutingTable(context)

    assert table.resolve("discord:123") == "cookie"


def test_routing_table_tier_priority():
    """More specific patterns should take priority."""
    context = MockContext(
        [
            {"agent": "pickle", "value": "telegram:.*"},  # tier 2
            {"agent": "cookie", "value": "telegram:123456"},  # tier 0
        ]
    )
    table = RoutingTable(context)

    # tier 0 should win even though tier 2 is listed first
    assert table.resolve("telegram:123456") == "cookie"


def test_routing_table_order_within_tier():
    """Within same tier, first pattern in config wins."""
    context = MockContext(
        [
            {"agent": "cookie", "value": "telegram:12.*"},
            {"agent": "pickle", "value": "telegram:1.*"},
        ]
    )
    table = RoutingTable(context)

    # Both tier 2, first one wins
    assert table.resolve("telegram:123456") == "cookie"


def test_routing_table_caches_bindings():
    """RoutingTable should cache compiled bindings."""
    context = MockContext(
        [
            {"agent": "pickle", "value": "telegram:.*"},
        ]
    )
    table = RoutingTable(context)

    # First call builds cache
    table.resolve("telegram:123")
    hash1 = table._config_hash

    # Second call uses cache
    table.resolve("telegram:456")
    assert table._config_hash == hash1


def test_routing_table_rebuilds_on_config_change():
    """RoutingTable should rebuild when config changes."""
    context = MockContext(
        [
            {"agent": "pickle", "value": "telegram:.*"},
        ]
    )
    table = RoutingTable(context)

    table.resolve("telegram:123")
    old_bindings = table._bindings

    # Change config
    context.config.routing["bindings"] = [{"agent": "cookie", "value": "telegram:.*"}]

    # Should rebuild
    table.resolve("telegram:123")
    assert table._bindings != old_bindings
    assert table.resolve("telegram:123") == "cookie"


def test_get_or_create_session_id_cache_hit(mock_context):
    """Test that existing session_id is returned from cache without creating new session."""
    from picklebot.channel.telegram_channel import TelegramEventSource
    from picklebot.core.routing import RoutingTable
    from unittest.mock import MagicMock

    # Setup
    routing = RoutingTable(mock_context)
    source = TelegramEventSource(user_id="123", chat_id="456")
    existing_session_id = "existing-session-789"

    # Ensure agent_loader is mocked
    mock_context.agent_loader = MagicMock()

    # Pre-populate cache - use a real dict instead of MagicMock
    mock_context.config.sources = {str(source): {"session_id": existing_session_id}}

    # Execute
    result = routing.get_or_create_session_id(source)

    # Verify
    assert result == existing_session_id
    # Ensure no new session was created
    mock_context.agent_loader.load.assert_not_called()


def test_get_or_create_session_id_creates_new_session(mock_context):
    """Test that new session is created when not in cache."""
    from picklebot.channel.telegram_channel import TelegramEventSource
    from picklebot.core.routing import RoutingTable
    from unittest.mock import MagicMock

    # Setup
    routing = RoutingTable(mock_context)
    source = TelegramEventSource(user_id="123", chat_id="456")
    new_session_id = "new-session-789"

    # Ensure cache is empty (cache-miss scenario)
    mock_context.config.sources = {}
    mock_context.config.default_agent = "test-agent"

    # Mock agent creation
    mock_agent_def = MagicMock()
    mock_context.agent_loader.load.return_value = mock_agent_def

    mock_session = MagicMock()
    mock_session.session_id = new_session_id

    mock_agent = MagicMock()
    mock_agent.new_session.return_value = mock_session

    # Mock Agent constructor
    with patch(
        "picklebot.core.routing.Agent", return_value=mock_agent
    ) as mock_agent_class:
        # Execute
        result = routing.get_or_create_session_id(source)

        # Verify
        assert result == new_session_id
        # Agent ID should be resolved from routing (default_agent)
        mock_context.agent_loader.load.assert_called_once_with("test-agent")
        mock_agent_class.assert_called_once_with(mock_agent_def, mock_context)
        mock_agent.new_session.assert_called_once_with(source)

        # Verify cache update
        expected_cache_key = f"sources.{str(source)}"
        mock_context.config.set_runtime.assert_called_once_with(
            expected_cache_key, {"session_id": new_session_id}
        )


def test_get_or_create_session_id_propagates_agent_not_found(mock_context):
    """Test that exceptions from agent loading are propagated."""
    from picklebot.channel.telegram_channel import TelegramEventSource
    from picklebot.core.routing import RoutingTable
    from unittest.mock import MagicMock

    # Setup
    routing = RoutingTable(mock_context)
    source = TelegramEventSource(user_id="123", chat_id="456")

    # Ensure cache is empty (cache-miss scenario)
    mock_context.config.sources = {}
    mock_context.config.default_agent = "nonexistent-agent"

    # Mock agent loader to raise exception
    mock_context.agent_loader = MagicMock()
    mock_context.agent_loader.load.side_effect = FileNotFoundError("Agent not found")

    # Execute & Verify
    with pytest.raises(FileNotFoundError, match="Agent not found"):
        routing.get_or_create_session_id(source)


# Test add_runtime_binding and clear_session_cache methods


@pytest.fixture
def routing_table(mock_context):
    """Create RoutingTable with mock context."""
    from picklebot.core.routing import RoutingTable

    # Setup mock context with necessary attributes
    mock_context.config.routing = {"bindings": []}
    mock_context.config.sources = {}

    return RoutingTable(mock_context)


def test_add_runtime_binding(routing_table, mock_context):
    """Test adding runtime binding."""
    # Setup: no existing bindings
    mock_context.config.routing = {"bindings": []}

    # Add binding
    routing_table.persist_binding("platform-telegram:user_123:chat_456", "cookie")

    # Verify binding added
    mock_context.config.set_runtime.assert_called_once_with(
        "routing.bindings",
        [{"agent": "cookie", "value": "platform-telegram:user_123:chat_456"}],
    )


def test_add_runtime_binding_appends_existing(routing_table, mock_context):
    """Test adding binding appends to existing bindings."""
    # Setup: existing binding
    mock_context.config.routing = {
        "bindings": [{"agent": "pickle", "value": "platform-cli:.*"}]
    }

    # Add new binding
    routing_table.persist_binding("platform-telegram:user_123:chat_456", "cookie")

    # Verify both bindings present
    mock_context.config.set_runtime.assert_called_once_with(
        "routing.bindings",
        [
            {"agent": "pickle", "value": "platform-cli:.*"},
            {"agent": "cookie", "value": "platform-telegram:user_123:chat_456"},
        ],
    )


def test_clear_session_cache(routing_table, mock_context):
    """Test clearing session cache for a source."""
    # Setup: source has cached session
    source_str = "platform-telegram:user_123:chat_456"
    mock_context.config.sources = {source_str: {"session_id": "existing-session-123"}}

    # Clear cache
    routing_table.clear_session_cache(source_str)

    # Verify source removed from dict and persisted
    assert source_str not in mock_context.config.sources
    mock_context.config.set_runtime.assert_called_once_with("sources", {})


def test_clear_session_cache_nonexistent(routing_table, mock_context):
    """Test clearing cache for nonexistent source is safe."""
    # Setup: no sources
    mock_context.config.sources = {}

    # Clear nonexistent source (should not error)
    routing_table.clear_session_cache("platform-telegram:user:chat")

    # Verify still empty
    assert len(mock_context.config.sources) == 0


def test_get_or_create_session_id_no_agent_id_param(routing_table, mock_context):
    """get_or_create_session_id should not require agent_id parameter."""
    from picklebot.core.events import CliEventSource
    from unittest.mock import MagicMock

    source = CliEventSource()

    # Mock agent creation
    mock_agent_def = MagicMock()
    mock_context.agent_loader.load.return_value = mock_agent_def

    mock_session = MagicMock()
    mock_session.session_id = "test-session-123"

    mock_agent = MagicMock()
    mock_agent.new_session.return_value = mock_session

    # Mock Agent constructor
    with patch("picklebot.core.routing.Agent", return_value=mock_agent):
        # Should work without agent_id parameter
        session_id = routing_table.get_or_create_session_id(source)

        assert session_id is not None
        assert isinstance(session_id, str)
        assert session_id == "test-session-123"


def test_get_or_create_session_id_resolves_agent_for_new_session(
    routing_table, mock_context
):
    """For new sessions, should resolve agent from routing table."""
    from picklebot.core.events import CliEventSource
    from unittest.mock import MagicMock

    source = CliEventSource()

    # Mock routing to return 'cookie' agent
    mock_context.config.routing = {"bindings": []}
    mock_context.config.default_agent = "cookie"

    # Mock agent creation
    mock_agent_def = MagicMock()
    mock_context.agent_loader.load.return_value = mock_agent_def

    mock_session = MagicMock()
    mock_session.session_id = "new-session-456"

    mock_agent = MagicMock()
    mock_agent.new_session.return_value = mock_session

    # Mock Agent constructor
    with patch("picklebot.core.routing.Agent", return_value=mock_agent):
        session_id = routing_table.get_or_create_session_id(source)

        # Verify it loaded the 'cookie' agent (from default_agent)
        mock_context.agent_loader.load.assert_called_once_with("cookie")
        assert session_id == "new-session-456"


def test_get_or_create_session_id_returns_cached_for_existing(
    routing_table, mock_context
):
    """For existing sessions, should return cached session_id."""
    from picklebot.core.events import CliEventSource

    source = CliEventSource()
    source_str = str(source)

    # Pre-cache a session
    existing_session_id = "existing-session-789"
    mock_context.config.sources = {source_str: {"session_id": existing_session_id}}

    # Now change routing to different agent
    mock_context.config.default_agent = "cookie"

    # Should return existing session without calling agent_loader
    returned_session_id = routing_table.get_or_create_session_id(source)

    assert returned_session_id == existing_session_id

    # Verify agent_loader was NOT called (cache hit)
    mock_context.agent_loader.load.assert_not_called()
