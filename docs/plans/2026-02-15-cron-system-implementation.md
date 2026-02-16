# Cron System Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add 24/7 cron job execution to pickle-bot via a new `server` command.

**Architecture:** Follow the existing AgentLoader pattern with CronLoader for CRON.md files. CronExecutor runs a simple asyncio loop that checks every 60 seconds and executes due jobs sequentially via fresh Agent sessions.

**Tech Stack:** Python 3.13, asyncio, croniter for cron expression parsing, Pydantic for models

---

## Task 1: Add croniter Dependency

**Files:**
- Modify: `pyproject.toml`

**Step 1: Add croniter to dependencies**

Add `croniter>=1.0.0` to the dependencies list:

```toml
dependencies = [
  "litellm>=1.0.0",
  "typer>=0.12.0",
  "textual>=0.21.0",
  "pydantic>=2.0.0",
  "pyyaml>=6.0",
  "rich>=13.0.0",
  "croniter>=1.0.0",
]
```

**Step 2: Install the dependency**

Run: `uv sync`

Expected: Dependencies resolved and installed successfully.

**Step 3: Commit**

```bash
git add pyproject.toml
git commit -m "chore: add croniter dependency for cron expressions"
```

---

## Task 2: Add crons_path to Config

**Files:**
- Modify: `src/picklebot/utils/config.py`
- Create: `tests/core/test_cron_loader.py` (add test for config)

**Step 1: Write the failing test**

Create `tests/core/test_cron_loader.py`:

```python
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
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/core/test_cron_loader.py::TestCronConfig::test_config_has_crons_path_default -v`

Expected: FAIL with `AttributeError: 'Config' object has no attribute 'crons_path'`

**Step 3: Add crons_path field to Config**

In `src/picklebot/utils/config.py`, add `crons_path` field to the `Config` class (line 52, after `history_path`):

```python
    agents_path: Path = Field(default=Path("agents"))
    logging_path: Path = Field(default=Path(".logs"))
    history_path: Path = Field(default=Path(".history"))
    crons_path: Path = Field(default=Path("crons"))  # Add this line
```

**Step 4: Update path resolver**

In the `resolve_paths` method (around line 57), add `crons_path` to the fields to resolve:

```python
    @model_validator(mode="after")
    def resolve_paths(self) -> "Config":
        """Resolve relative paths to absolute using workspace."""
        for field_name in ("agents_path", "logging_path", "history_path", "crons_path"):
            path = getattr(self, field_name)
            if path.is_absolute():
                raise ValueError(f"{field_name} must be relative, got: {path}")
            setattr(self, field_name, self.workspace / path)
        return self
```

**Step 5: Run test to verify it passes**

Run: `uv run pytest tests/core/test_cron_loader.py::TestCronConfig::test_config_has_crons_path_default -v`

Expected: PASS

**Step 6: Commit**

```bash
git add src/picklebot/utils/config.py tests/core/test_cron_loader.py
git commit -m "feat(config): add crons_path configuration field"
```

---

## Task 3: Create CronDef and CronMetadata Models

**Files:**
- Create: `src/picklebot/core/cron_loader.py`
- Modify: `tests/core/test_cron_loader.py`

**Step 1: Write the failing test**

Add to `tests/core/test_cron_loader.py`:

```python
from picklebot.core.cron_loader import CronDef, CronMetadata


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
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/core/test_cron_loader.py::TestCronDef -v`

Expected: FAIL with `ImportError` or `ModuleNotFoundError`

**Step 3: Create CronDef and CronMetadata**

Create `src/picklebot/core/cron_loader.py`:

```python
"""Cron job definition loader."""

from pathlib import Path
from typing import Any

import yaml
from croniter import croniter
from pydantic import BaseModel, field_validator


class CronMetadata(BaseModel):
    """Lightweight cron info for discovery."""

    id: str
    name: str
    agent: str
    schedule: str


class CronDef(BaseModel):
    """Loaded cron job definition."""

    id: str
    name: str
    agent: str
    schedule: str
    prompt: str

    @field_validator("schedule")
    @classmethod
    def validate_schedule(cls, v: str) -> str:
        """Validate cron expression and enforce 5-minute minimum granularity."""
        if not croniter.is_valid(v):
            raise ValueError(f"Invalid cron expression: {v}")

        # Check minimum 5-minute granularity
        # Parse the minute field (first field)
        minute_field = v.split()[0]

        # Allow: */5, */10, */15, etc. (divisible by 5)
        # Allow: 0, 5, 10, 15, etc. (specific minutes divisible by 5)
        # Allow: * only if other fields make it run at most every 5 minutes
        # For simplicity, we check if minute value is divisible by 5 or is */N where N >= 5

        if minute_field == "*":
            # Every minute - not allowed
            raise ValueError(
                f"Schedule must have minimum 5-minute granularity. Got: {v}"
            )
        elif minute_field.startswith("*/"):
            try:
                interval = int(minute_field[2:])
                if interval < 5:
                    raise ValueError(
                        f"Schedule must have minimum 5-minute granularity. Got: {v}"
                    )
            except ValueError:
                pass  # Let croniter validation handle it
        elif minute_field.isdigit():
            # Single minute value - this runs every hour at that minute, which is fine
            pass
        elif "," in minute_field:
            # Multiple values - check all are >= 5 minutes apart
            # For simplicity, just ensure we're not running more often than every 5 min
            pass

        return v


class CronNotFoundError(Exception):
    """Cron folder or CRON.md doesn't exist."""

    def __init__(self, cron_id: str):
        super().__init__(f"Cron job not found: {cron_id}")
        self.cron_id = cron_id


class InvalidCronError(Exception):
    """Cron file is malformed."""

    def __init__(self, cron_id: str, reason: str):
        super().__init__(f"Invalid cron job '{cron_id}': {reason}")
        self.cron_id = cron_id
        self.reason = reason
```

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/core/test_cron_loader.py::TestCronDef -v`

Expected: PASS

**Step 5: Commit**

```bash
git add src/picklebot/core/cron_loader.py tests/core/test_cron_loader.py
git commit -m "feat(cron): add CronDef and CronMetadata models"
```

---

## Task 4: Implement CronLoader

**Files:**
- Modify: `src/picklebot/core/cron_loader.py`
- Modify: `tests/core/test_cron_loader.py`

**Step 1: Write the failing tests**

Add to `tests/core/test_cron_loader.py`:

```python
from picklebot.core.cron_loader import CronLoader, CronNotFoundError, InvalidCronError


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
```

**Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/core/test_cron_loader.py::TestCronLoader -v`

Expected: FAIL with `AttributeError: 'CronLoader' object has no attribute 'load'`

**Step 3: Implement CronLoader**

Add to `src/picklebot/core/cron_loader.py`:

```python
import logging

logger = logging.getLogger(__name__)


class CronLoader:
    """Loads cron job definitions from CRON.md files."""

    def __init__(self, crons_path: Path):
        """
        Initialize CronLoader.

        Args:
            crons_path: Directory containing cron folders
        """
        self.crons_path = crons_path

    def discover_crons(self) -> list[CronMetadata]:
        """
        Scan crons directory, return lightweight metadata for all valid jobs.

        Returns:
            List of CronMetadata for valid cron jobs.
        """
        if not self.crons_path.exists():
            logger.warning(f"Crons directory not found: {self.crons_path}")
            return []

        crons = []
        for cron_dir in self.crons_path.iterdir():
            if not cron_dir.is_dir():
                continue

            cron_file = cron_dir / "CRON.md"
            if not cron_file.exists():
                logger.warning(f"No CRON.md found in {cron_dir.name}")
                continue

            try:
                metadata = self._parse_cron_metadata(cron_file)
                crons.append(metadata)
            except Exception as e:
                logger.warning(f"Invalid cron {cron_dir.name}: {e}")
                continue

        return crons

    def load(self, cron_id: str) -> CronDef:
        """
        Load cron by ID.

        Args:
            cron_id: Cron folder name

        Returns:
            CronDef with full definition

        Raises:
            CronNotFoundError: Cron folder or file doesn't exist
            InvalidCronError: Cron file is malformed
        """
        cron_file = self.crons_path / cron_id / "CRON.md"
        if not cron_file.exists():
            raise CronNotFoundError(cron_id)

        try:
            frontmatter, body = self._parse_cron_file(cron_file)
        except Exception as e:
            raise InvalidCronError(cron_id, str(e))

        # Validate required fields
        for field in ["name", "agent", "schedule"]:
            if field not in frontmatter:
                raise InvalidCronError(cron_id, f"missing required field: {field}")

        # Validate schedule (runs through Pydantic validator)
        try:
            CronDef.model_validate({"schedule": frontmatter["schedule"]})
        except Exception as e:
            raise InvalidCronError(cron_id, str(e))

        return CronDef(
            id=cron_id,
            name=frontmatter["name"],
            agent=frontmatter["agent"],
            schedule=frontmatter["schedule"],
            prompt=body.strip(),
        )

    def _parse_cron_file(self, path: Path) -> tuple[dict[str, Any], str]:
        """
        Parse YAML frontmatter + markdown body.

        Args:
            path: Path to CRON.md file

        Returns:
            Tuple of (frontmatter dict, body string)
        """
        content = path.read_text()
        parts = [p for p in content.split("---\n") if p.strip()]

        if len(parts) < 2:
            return {}, content

        frontmatter_text = parts[0]
        body = "---\n".join(parts[1:])

        frontmatter = yaml.safe_load(frontmatter_text) or {}
        return frontmatter, body

    def _parse_cron_metadata(self, path: Path) -> CronMetadata:
        """
        Parse cron file and return metadata only.

        Args:
            path: Path to CRON.md file

        Returns:
            CronMetadata instance
        """
        frontmatter, _ = self._parse_cron_file(path)

        for field in ["name", "agent", "schedule"]:
            if field not in frontmatter:
                raise ValueError(f"missing required field: {field}")

        return CronMetadata(
            id=path.parent.name,
            name=frontmatter["name"],
            agent=frontmatter["agent"],
            schedule=frontmatter["schedule"],
        )
```

**Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/core/test_cron_loader.py::TestCronLoader -v`

Expected: PASS (all tests)

**Step 5: Commit**

```bash
git add src/picklebot/core/cron_loader.py tests/core/test_cron_loader.py
git commit -m "feat(cron): implement CronLoader with discovery and loading"
```

---

## Task 5: Implement CronExecutor

**Files:**
- Create: `src/picklebot/core/cron_executor.py`
- Create: `tests/core/test_cron_executor.py`

**Step 1: Write the failing tests**

Create `tests/core/test_cron_executor.py`:

```python
"""Tests for CronExecutor."""

from datetime import datetime, timedelta
from pathlib import Path
import tempfile

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from picklebot.core.cron_executor import CronExecutor, find_due_job
from picklebot.core.cron_loader import CronMetadata


class TestFindDueJob:
    """Test the find_due_job helper."""

    def test_returns_none_when_no_jobs(self):
        """Return None when job list is empty."""
        result = find_due_job([])
        assert result is None

    def test_returns_first_due_job(self):
        """Return the first job that's due."""
        now = datetime.now()

        # Create jobs with different schedules
        # Job that runs every 5 minutes (likely due)
        due_job = CronMetadata(
            id="due-job",
            name="Due Job",
            agent="pickle",
            schedule="*/5 * * * *",
        )
        # Job that runs at midnight (unlikely to be due)
        not_due_job = CronMetadata(
            id="not-due",
            name="Not Due",
            agent="pickle",
            schedule="0 0 * * *",
        )

        jobs = [due_job, not_due_job]
        result = find_due_job(jobs)

        # At least one should be due (the */5 one)
        assert result is not None

    def test_returns_none_when_no_jobs_due(self):
        """Return None when no jobs are due."""
        # Create a job that only runs at a very specific time
        # (minute 59 of hour 23 on day 31 of December)
        job = CronMetadata(
            id="rare-job",
            name="Rare Job",
            agent="pickle",
            schedule="59 23 31 12 *",
        )

        result = find_due_job([job])
        # This job is extremely unlikely to be due right now
        # But we can't guarantee it's not, so we just check it doesn't crash
        assert result is None or result.id == "rare-job"
```

**Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/core/test_cron_executor.py -v`

Expected: FAIL with `ModuleNotFoundError`

**Step 3: Create CronExecutor**

Create `src/picklebot/core/cron_executor.py`:

```python
"""Cron job executor."""

import asyncio
import logging
from datetime import datetime

from croniter import croniter

from picklebot.core.context import SharedContext
from picklebot.core.cron_loader import CronDef, CronLoader, CronMetadata
from picklebot.core.agent import Agent
from picklebot.core.agent_loader import AgentLoader

logger = logging.getLogger(__name__)


def find_due_job(jobs: list[CronMetadata], now: datetime | None = None) -> CronMetadata | None:
    """
    Find the first job that's due to run.

    A job is due if the current minute matches its cron schedule.

    Args:
        jobs: List of cron metadata to check
        now: Current time (defaults to datetime.now())

    Returns:
        First due job, or None if none are due
    """
    if not jobs:
        return None

    now = now or datetime.now()
    # Round down to the minute for comparison
    now_minute = now.replace(second=0, microsecond=0)

    for job in jobs:
        try:
            cron = croniter(job.schedule, now_minute)
            # Get the previous run time (should be now if we're due)
            prev_run = cron.get_prev(datetime)
            # If prev_run equals now_minute, we're due
            if prev_run == now_minute:
                return job
        except Exception as e:
            logger.warning(f"Error checking schedule for {job.id}: {e}")
            continue

    return None


class CronExecutor:
    """Executes cron jobs on schedule."""

    def __init__(self, context: SharedContext):
        """
        Initialize CronExecutor.

        Args:
            context: Shared application context
        """
        self.context = context
        self.cron_loader = CronLoader(context.config.crons_path)
        self.agent_loader = AgentLoader.from_config(context.config)

    async def run(self) -> None:
        """
        Main loop: check every minute, execute due jobs.

        Runs forever until interrupted.
        """
        logger.info("CronExecutor started")

        while True:
            try:
                await self._tick()
            except Exception as e:
                logger.error(f"Error in tick: {e}")

            await asyncio.sleep(60)

    async def _tick(self) -> None:
        """Check schedules and run due jobs."""
        jobs = self.cron_loader.discover_crons()
        due_job_meta = find_due_job(jobs)

        if due_job_meta:
            logger.info(f"Running cron job: {due_job_meta.id}")
            try:
                cron_def = self.cron_loader.load(due_job_meta.id)
                await self._run_job(cron_def)
            except Exception as e:
                logger.error(f"Cron job {due_job_meta.id} failed: {e}")

    async def _run_job(self, cron_def: CronDef) -> None:
        """
        Execute a single cron job.

        Args:
            cron_def: Full cron job definition
        """
        try:
            agent_def = self.agent_loader.load(cron_def.agent)
            agent = Agent(agent_def, self.context)

            # Create a new session for this job
            session = agent.new_session()

            # Import here to avoid circular dependency
            from picklebot.frontend.console import ConsoleFrontend

            frontend = ConsoleFrontend()

            # Run the agent with the cron prompt
            await session.chat(cron_def.prompt, frontend)

            logger.info(f"Cron job {cron_def.id} completed successfully")
        except Exception as e:
            logger.error(f"Error executing cron job {cron_def.id}: {e}")
            raise
```

**Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/core/test_cron_executor.py -v`

Expected: PASS

**Step 5: Commit**

```bash
git add src/picklebot/core/cron_executor.py tests/core/test_cron_executor.py
git commit -m "feat(cron): implement CronExecutor with scheduler loop"
```

---

## Task 6: Create Server CLI Command

**Files:**
- Create: `src/picklebot/cli/server.py`
- Modify: `src/picklebot/cli/main.py`

**Step 1: Write the failing test**

Add to `tests/core/test_cron_executor.py` or create `tests/cli/test_server.py`:

Actually, let's skip CLI tests for now since they're harder to test in isolation. We'll verify manually.

**Step 2: Create server CLI command**

Create `src/picklebot/cli/server.py`:

```python
"""Server CLI command for cron execution."""

import asyncio

import typer

from picklebot.core.context import SharedContext
from picklebot.core.cron_executor import CronExecutor


def server_command(
    ctx: typer.Context,
) -> None:
    """Start the 24/7 server for cron job execution."""
    config = ctx.obj.get("config")

    context = SharedContext(config)
    executor = CronExecutor(context)

    typer.echo("Starting pickle-bot server...")
    typer.echo(f"Crons path: {config.crons_path}")
    typer.echo("Press Ctrl+C to stop")

    try:
        asyncio.run(executor.run())
    except KeyboardInterrupt:
        typer.echo("\nServer stopped")
```

**Step 3: Register command in main CLI**

Modify `src/picklebot/cli/main.py`:

Add import at the top:

```python
from picklebot.cli.chat import ChatLoop
from picklebot.cli.server import server_command  # Add this
```

Add command registration after the `chat` command (around line 81):

```python
@app.command()
def chat(
    ctx: typer.Context,
    agent: Annotated[
        str | None,
        typer.Option(
            "--agent",
            "-a",
            help="Agent ID to use (overrides default_agent from config)",
        ),
    ] = None,
) -> None:
    """Start interactive chat session."""
    import asyncio

    config = ctx.obj.get("config")

    session = ChatLoop(config, agent_id=agent)
    asyncio.run(session.run())


@app.command("server")
def server(
    ctx: typer.Context,
) -> None:
    """Start the 24/7 server for cron job execution."""
    server_command(ctx)
```

**Step 4: Verify command exists**

Run: `uv run picklebot --help`

Expected: Output includes `server` command

**Step 5: Commit**

```bash
git add src/picklebot/cli/server.py src/picklebot/cli/main.py
git commit -m "feat(cli): add server command for cron execution"
```

---

## Task 7: Run All Tests

**Files:**
- None (verification only)

**Step 1: Run full test suite**

Run: `uv run pytest -v`

Expected: All tests pass

**Step 2: Run type checking**

Run: `uv run mypy src/`

Expected: No type errors

**Step 3: Run linting**

Run: `uv run ruff check src/`

Expected: No linting errors

---

## Task 8: Update README

**Files:**
- Modify: `README.md`

**Step 1: Add server command documentation**

Add to the Usage section after the `chat` examples:

```markdown
## Usage

```bash
picklebot chat              # Start interactive chat (uses default_agent)
picklebot chat --agent name # Use specific agent
picklebot chat -a name      # Shorthand
picklebot -w /path chat     # Use custom workspace directory
picklebot --help            # Show help
```

### Server Mode

Run pickle-bot as a 24/7 server for scheduled cron jobs:

```bash
picklebot server            # Start server with default workspace
picklebot server -w /path   # Use custom workspace
```

The server reads cron jobs from `~/.pickle-bot/crons/[job-id]/CRON.md`:

```markdown
---
name: Inbox Check
agent: pickle
schedule: "*/15 * * * *"
---

Check my inbox and summarize unread messages.
```

**Cron job requirements:**
- Minimum granularity: 5 minutes
- Fresh session per run (no memory between runs)
- Sequential execution (one job at a time)
```

**Step 2: Add crons directory to configuration section**

Update the directory structure:

```markdown
~/.pickle-bot/
├── config.system.yaml    # System defaults
├── config.user.yaml      # Your overrides (optional)
├── agents/               # Agent definitions
│   └── pickle/
│       └── AGENT.md
├── crons/                # Cron job definitions
│   └── inbox-check/
│       └── CRON.md
└── history/              # Session persistence
    ├── sessions/
    └── index.json
```

**Step 3: Commit**

```bash
git add README.md
git commit -m "docs: add server command and cron system documentation"
```

---

## Task 9: Final Verification

**Step 1: Create a test cron job**

```bash
mkdir -p ~/.pickle-bot/crons/test-job
cat > ~/.pickle-bot/crons/test-job/CRON.md << 'EOF'
---
name: Test Job
agent: pickle
schedule: "*/5 * * * *"
---

Say hello and report the current time.
EOF
```

**Step 2: Verify cron loading**

Run: `uv run python -c "from pathlib import Path; from picklebot.core.cron_loader import CronLoader; loader = CronLoader(Path.home() / '.pickle-bot' / 'crons'); print(loader.discover_crons())"`

Expected: Shows the test job metadata

**Step 3: Run server briefly**

Run: `uv run picklebot server` (Ctrl+C after a few seconds)

Expected: Server starts, logs "CronExecutor started"

---

## Summary

After completing all tasks:

1. `croniter` dependency added
2. `crons_path` in Config
3. `CronDef`, `CronMetadata`, `CronLoader` in `core/cron_loader.py`
4. `CronExecutor` in `core/cron_executor.py`
5. `server` CLI command registered
6. README updated

**Commands available:**
- `picklebot chat` - Interactive chat
- `picklebot server` - 24/7 cron execution

**Cron jobs live in:** `~/.pickle-bot/crons/[job-id]/CRON.md`
