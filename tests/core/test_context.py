from picklebot.core.context import SharedContext
from picklebot.core.history import HistoryStore
from picklebot.utils.config import Config


def test_shared_context_holds_config_and_history_store(tmp_path):
    """SharedContext should hold config and history_store."""
    # Create minimal config file
    config_file = tmp_path / "config.system.yaml"
    config_file.write_text(
        """
llm:
  provider: test
  model: test-model
  api_key: test-key
"""
    )

    config = Config.load(tmp_path)
    history_store = HistoryStore.from_config(config)

    context = SharedContext(config=config, history_store=history_store)

    assert context.config is config
    assert context.history_store is history_store
