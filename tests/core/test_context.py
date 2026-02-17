"""Tests for SharedContext."""


def test_shared_context_holds_config_and_history_store(test_context):
    """SharedContext should hold config and history_store."""
    assert test_context.config is not None
    assert test_context.history_store is not None
    assert test_context.agent_loader is not None
