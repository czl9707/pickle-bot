from picklebot.core.context import SharedContext
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
default_agent: test-agent
"""
    )

    config = Config.load(tmp_path)
    context = SharedContext(config=config)

    assert context.config is config
    assert context.history_store is not None
