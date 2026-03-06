# tests/core/test_routing.py

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
    agent_id = "test-agent"
    existing_session_id = "existing-session-789"

    # Ensure agent_loader is mocked
    mock_context.agent_loader = MagicMock()

    # Pre-populate cache
    mock_context.config.sources[str(source)] = {"session_id": existing_session_id}

    # Execute
    result = routing.get_or_create_session_id(source, agent_id)

    # Verify
    assert result == existing_session_id
    # Ensure no new session was created
    mock_context.agent_loader.load.assert_not_called()
