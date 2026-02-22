"""Tests for CronLoader and related components."""


from picklebot.core.cron_loader import CronLoader


class TestCronLoader:
    """Test CronLoader class."""

    def test_load_simple_cron(self, test_config):
        """Parse cron with required fields."""
        crons_dir = test_config.crons_path
        crons_dir.mkdir(parents=True, exist_ok=True)

        cron_dir = crons_dir / "inbox-check"
        cron_dir.mkdir()
        (cron_dir / "CRON.md").write_text(
            "---\n"
            "name: Inbox Check\n"
            "agent: pickle\n"
            "schedule: '*/15 * * * *'\n"
            "---\n"
            "Check my inbox and summarize."
        )

        loader = CronLoader(test_config)
        cron_def = loader.load("inbox-check")

        assert cron_def.id == "inbox-check"
        assert cron_def.name == "Inbox Check"
        assert cron_def.agent == "pickle"
        assert cron_def.schedule == "*/15 * * * *"
        assert cron_def.prompt == "Check my inbox and summarize."

    def test_discover_crons(self, test_config):
        """Discover all valid cron jobs."""
        crons_dir = test_config.crons_path
        crons_dir.mkdir(parents=True, exist_ok=True)

        # Create two valid cron jobs
        for name, schedule in [("job-a", "*/5 * * * *"), ("job-b", "0 * * * *")]:
            cron_dir = crons_dir / name
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
        (crons_dir / "no-file").mkdir()

        loader = CronLoader(test_config)
        defs = loader.discover_crons()

        assert len(defs) == 2
        ids = [d.id for d in defs]
        assert "job-a" in ids
        assert "job-b" in ids
        assert "no-file" not in ids

        for d in defs:
            assert d.prompt.startswith("Do ")
            assert d.id in d.prompt

    def test_substitutes_template_variables(self, test_config):
        """Cron prompt can use template variables."""
        crons_dir = test_config.crons_path
        crons_dir.mkdir(parents=True, exist_ok=True)

        cron_dir = crons_dir / "test-cron"
        cron_dir.mkdir()
        (cron_dir / "CRON.md").write_text(
            "---\n"
            "name: Test Cron\n"
            "agent: pickle\n"
            "schedule: '0 * * * *'\n"
            "---\n"
            "Check memories at {{memories_path}}"
        )

        loader = CronLoader(test_config)
        cron_def = loader.load("test-cron")

        expected = f"Check memories at {test_config.memories_path}"
        assert cron_def.prompt == expected

    def test_load_cron_with_one_off(self, test_config):
        """Parse cron with one_off field."""
        crons_dir = test_config.crons_path
        crons_dir.mkdir(parents=True, exist_ok=True)

        cron_dir = crons_dir / "one-time"
        cron_dir.mkdir()
        (cron_dir / "CRON.md").write_text(
            "---\n"
            "name: One Time\n"
            "agent: pickle\n"
            "schedule: '0 10 18 2 *'\n"
            "one_off: true\n"
            "---\n"
            "Remind me once."
        )

        loader = CronLoader(test_config)
        cron_def = loader.load("one-time")

        assert cron_def.one_off is True

    def test_discover_crons_with_one_off(self, test_config):
        """Discover crons includes one_off field."""
        crons_dir = test_config.crons_path
        crons_dir.mkdir(parents=True, exist_ok=True)

        # Create a one-off cron
        cron_dir = crons_dir / "one-off-job"
        cron_dir.mkdir()
        (cron_dir / "CRON.md").write_text(
            "---\n"
            "name: One Off Job\n"
            "agent: pickle\n"
            "schedule: '*/5 * * * *'\n"
            "one_off: true\n"
            "---\n"
            "Do once."
        )

        # Create a recurring cron (no one_off field)
        cron_dir2 = crons_dir / "recurring-job"
        cron_dir2.mkdir()
        (cron_dir2 / "CRON.md").write_text(
            "---\n"
            "name: Recurring Job\n"
            "agent: pickle\n"
            "schedule: '0 * * * *'\n"
            "---\n"
            "Do repeatedly."
        )

        loader = CronLoader(test_config)
        defs = loader.discover_crons()

        assert len(defs) == 2
        one_off = next(d for d in defs if d.id == "one-off-job")
        recurring = next(d for d in defs if d.id == "recurring-job")

        assert one_off.one_off is True
        assert recurring.one_off is False
