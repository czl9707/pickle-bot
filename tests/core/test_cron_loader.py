"""Tests for CronLoader and related components."""

from pathlib import Path
import tempfile

import pytest

from picklebot.core.cron_loader import (
    CronLoader,
    CronNotFoundError,
    InvalidCronError,
)
from picklebot.utils.def_loader import DefNotFoundError, InvalidDefError


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

    def test_raises_not_found(self, temp_crons_dir):
        """Raise CronNotFoundError when cron doesn't exist."""
        loader = CronLoader(temp_crons_dir)

        with pytest.raises(CronNotFoundError) as exc:
            loader.load("nonexistent")

        # CronNotFoundError is an alias for DefNotFoundError
        assert exc.value.def_id == "nonexistent"
        assert exc.value.kind == "cron"

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

        # InvalidCronError is an alias for InvalidDefError
        assert "name" in exc.value.reason
        assert exc.value.def_id == "bad-cron"
        assert exc.value.kind == "cron"

    def test_error_aliases(self):
        """Verify error aliases are correct."""
        # CronNotFoundError is an alias for DefNotFoundError
        assert CronNotFoundError is DefNotFoundError
        # InvalidCronError is an alias for InvalidDefError
        assert InvalidCronError is InvalidDefError
