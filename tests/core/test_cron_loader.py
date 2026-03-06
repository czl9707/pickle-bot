"""Tests for CronLoader and related components."""

import pytest
from pydantic import ValidationError

from picklebot.core.cron_loader import CronDef, CronLoader


def test_cron_def_requires_description(tmp_path):
    """CronDef should require description field."""
    with pytest.raises(ValidationError) as exc_info:
        CronDef(
            id="test",
            name="Test Cron",
            agent="pickle",
            schedule="0 * * * *",
            prompt="Test prompt",
        )

    assert "description" in str(exc_info.value)


class TestCronLoader:
    """Test CronLoader class."""

    @pytest.mark.parametrize(
        "one_off,expected_one_off",
        [
            (None, False),  # default
            (True, True),  # explicit true
        ],
    )
    def test_load_cron_with_optional_fields(
        self, test_config, one_off, expected_one_off
    ):
        """Load cron with various field combinations."""
        crons_dir = test_config.crons_path
        crons_dir.mkdir(parents=True, exist_ok=True)

        cron_dir = crons_dir / "test-cron"
        cron_dir.mkdir()

        one_off_yaml = f"one_off: {one_off}\n" if one_off is not None else ""
        (cron_dir / "CRON.md").write_text(
            f"---\n"
            f"name: Test Cron\n"
            f"description: Test description\n"
            f"agent: pickle\n"
            f"schedule: '*/15 * * * *'\n"
            f"{one_off_yaml}"
            f"---\n"
            f"Test prompt."
        )

        loader = CronLoader(test_config)
        cron_def = loader.load("test-cron")

        assert cron_def.id == "test-cron"
        assert cron_def.name == "Test Cron"
        assert cron_def.agent == "pickle"
        assert cron_def.schedule == "*/15 * * * *"
        assert cron_def.one_off == expected_one_off

    def test_substitutes_template_variables(self, test_config):
        """Cron prompt can use template variables."""
        crons_dir = test_config.crons_path
        crons_dir.mkdir(parents=True, exist_ok=True)

        cron_dir = crons_dir / "test-cron"
        cron_dir.mkdir()
        (cron_dir / "CRON.md").write_text(
            "---\n"
            "name: Test Cron\n"
            "description: Test template substitution\n"
            "agent: pickle\n"
            "schedule: '0 * * * *'\n"
            "---\n"
            "Check memories at {{memories_path}}"
        )

        loader = CronLoader(test_config)
        cron_def = loader.load("test-cron")

        expected = f"Check memories at {test_config.memories_path}"
        assert cron_def.prompt == expected

    def test_discover_crons(self, test_config):
        """Discover all valid cron jobs including one_off variations."""
        crons_dir = test_config.crons_path
        crons_dir.mkdir(parents=True, exist_ok=True)

        # Create recurring cron
        cron_dir = crons_dir / "recurring-job"
        cron_dir.mkdir()
        (cron_dir / "CRON.md").write_text(
            "---\n"
            "name: Recurring Job\n"
            "description: A recurring job\n"
            "agent: pickle\n"
            "schedule: '*/5 * * * *'\n"
            "---\n"
            "Do repeatedly."
        )

        # Create one-off cron
        cron_dir2 = crons_dir / "one-off-job"
        cron_dir2.mkdir()
        (cron_dir2 / "CRON.md").write_text(
            "---\n"
            "name: One Off Job\n"
            "description: A one-off job\n"
            "agent: pickle\n"
            "schedule: '0 10 18 2 *'\n"
            "one_off: true\n"
            "---\n"
            "Do once."
        )

        # Create a directory without CRON.md (should be skipped)
        (crons_dir / "no-file").mkdir()

        loader = CronLoader(test_config)
        defs = loader.discover_crons()

        assert len(defs) == 2
        ids = [d.id for d in defs]
        assert "recurring-job" in ids
        assert "one-off-job" in ids
        assert "no-file" not in ids

        recurring = next(d for d in defs if d.id == "recurring-job")
        one_off = next(d for d in defs if d.id == "one-off-job")

        assert recurring.one_off is False
        assert one_off.one_off is True
