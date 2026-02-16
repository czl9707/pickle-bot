"""Tests for CronLoader and related components."""

from pathlib import Path
import tempfile

import pytest

from picklebot.utils.config import Config, LLMConfig


class TestCronConfig:
    """Test cron-related configuration."""

    def test_config_has_crons_path_default(self):
        """Config should have crons_path with default value."""
        with tempfile.TemporaryDirectory() as tmpdir:
            workspace = Path(tmpdir)
            (workspace / "config.system.yaml").write_text(
                "default_agent: pickle\n"
                "llm:\n"
                "  provider: test\n"
                "  model: test-model\n"
                "  api_key: test-key\n"
            )

            config = Config.load(workspace)

            assert config.crons_path == workspace / "crons"
