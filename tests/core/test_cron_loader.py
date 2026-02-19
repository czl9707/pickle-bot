"""Tests for CronLoader and related components."""

from pathlib import Path

import pytest

from picklebot.core.cron_loader import CronLoader


class TestCronLoader:
    """Test CronLoader class."""

    def test_load_simple_cron(self, temp_crons_dir: Path):
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

    def test_discover_crons(self, temp_crons_dir: Path):
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
        defs = loader.discover_crons()

        assert len(defs) == 2
        ids = [d.id for d in defs]
        assert "job-a" in ids
        assert "job-b" in ids
        assert "no-file" not in ids

        # Check that prompt field is populated
        for d in defs:
            assert d.prompt.startswith("Do ")
            assert d.id in d.prompt
