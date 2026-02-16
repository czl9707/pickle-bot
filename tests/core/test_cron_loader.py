"""Tests for CronLoader and related components."""

from pathlib import Path
import tempfile

import pytest

from picklebot.core.cron_loader import CronDef, CronMetadata
from picklebot.utils.config import Config, LLMConfig


class TestCronDef:
    """Test CronDef model."""

    def test_cron_def_basic(self):
        """CronDef should have required fields."""
        cron = CronDef(
            id="test-job",
            name="Test Job",
            agent="pickle",
            schedule="*/15 * * * *",
            prompt="Do something",
        )

        assert cron.id == "test-job"
        assert cron.name == "Test Job"
        assert cron.agent == "pickle"
        assert cron.schedule == "*/15 * * * *"
        assert cron.prompt == "Do something"

    def test_cron_metadata_basic(self):
        """CronMetadata should have discovery fields."""
        meta = CronMetadata(
            id="test-job",
            name="Test Job",
            agent="pickle",
            schedule="*/15 * * * *",
        )

        assert meta.id == "test-job"
        assert meta.name == "Test Job"


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
