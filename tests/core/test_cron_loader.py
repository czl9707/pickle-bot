"""Tests for CronLoader and related components."""

from pathlib import Path
import tempfile

import pytest

from picklebot.core.cron_loader import (
    CronLoader,
    CronNotFoundError,
    InvalidCronError,
    CronDef,
    CronMetadata,
)
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


class TestCronLoader:
    """Test CronLoader class."""

    @pytest.fixture
    def temp_crons_dir(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    def test_load_simple_cron(self, temp_crons_dir):
        """Parse cron with required fields."""
        cron_dir = temp_crons_dir / "inbox-check"
        cron_dir.mkdir()
        (cron_dir / "CRON.md").write_text(
            "---\n"
            "name: Inbox Check\n"
            "agent: pickle\n"
            "schedule: '*/15 * * * *'\n"
            "---\n"
            "Check my inbox and summarize."
        )

        loader = CronLoader(temp_crons_dir)
        cron_def = loader.load("inbox-check")

        assert cron_def.id == "inbox-check"
        assert cron_def.name == "Inbox Check"
        assert cron_def.agent == "pickle"
        assert cron_def.schedule == "*/15 * * * *"
        assert cron_def.prompt == "Check my inbox and summarize."

    def test_discover_crons(self, temp_crons_dir):
        """Discover all valid cron jobs."""
        # Create two valid cron jobs
        for name, schedule in [("job-a", "*/5 * * * *"), ("job-b", "0 * * * *")]:
            cron_dir = temp_crons_dir / name
            cron_dir.mkdir()
            (cron_dir / "CRON.md").write_text(
                f"---\n"
                f"name: {name}\n"
                f"agent: pickle\n"
                f"schedule: '{schedule}'\n"
                f"---\n"
                f"Do {name}"
            )

        # Create a directory without CRON.md (should be skipped)
        (temp_crons_dir / "no-file").mkdir()

        loader = CronLoader(temp_crons_dir)
        metas = loader.discover_crons()

        assert len(metas) == 2
        ids = [m.id for m in metas]
        assert "job-a" in ids
        assert "job-b" in ids
        assert "no-file" not in ids

    def test_raises_not_found(self, temp_crons_dir):
        """Raise CronNotFoundError when cron doesn't exist."""
        loader = CronLoader(temp_crons_dir)

        with pytest.raises(CronNotFoundError) as exc:
            loader.load("nonexistent")

        assert exc.value.cron_id == "nonexistent"

    def test_raises_invalid_missing_name(self, temp_crons_dir):
        """Raise InvalidCronError when name is missing."""
        cron_dir = temp_crons_dir / "bad-cron"
        cron_dir.mkdir()
        (cron_dir / "CRON.md").write_text(
            "---\n"
            "agent: pickle\n"
            "schedule: '*/15 * * * *'\n"
            "---\n"
            "Do something"
        )

        loader = CronLoader(temp_crons_dir)

        with pytest.raises(InvalidCronError) as exc:
            loader.load("bad-cron")

        assert "name" in exc.value.reason
