# One-Off Cron Jobs Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add `one_off` option to cron jobs so they auto-delete after successful execution.

**Architecture:** Add optional `one_off: bool` field to `CronDef` model, parse it in `CronLoader`, and delete cron folder in `CronExecutor` after successful run if `one_off=True`.

**Tech Stack:** Python, Pydantic, pytest

---

## Task 1: Add one_off Field to CronDef

**Files:**
- Modify: `src/picklebot/core/cron_loader.py:23-31`
- Test: `tests/core/test_cron_loader.py`

**Step 1: Write the failing test**

Add to `tests/core/test_cron_loader.py` in `TestCronLoader` class:

```python
def test_load_cron_with_one_off(self, temp_crons_dir):
    """Parse cron with one_off field."""
    cron_dir = temp_crons_dir / "one-time"
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

    loader = CronLoader(temp_crons_dir)
    cron_def = loader.load("one-time")

    assert cron_def.one_off is True
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/core/test_cron_loader.py::TestCronLoader::test_load_cron_with_one_off -v`
Expected: FAIL with "CronDef" has no field "one_off" or validation error

**Step 3: Write minimal implementation**

In `src/picklebot/core/cron_loader.py`, update `CronDef` class:

```python
class CronDef(BaseModel):
    """Loaded cron job definition."""

    id: str
    name: str
    agent: str
    schedule: str
    prompt: str
    one_off: bool = False
```

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/core/test_cron_loader.py::TestCronLoader::test_load_cron_with_one_off -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/picklebot/core/cron_loader.py tests/core/test_cron_loader.py
git commit -m "feat(cron): add one_off field to CronDef"
```

---

## Task 2: Update CronLoader to Parse one_off

**Files:**
- Modify: `src/picklebot/core/cron_loader.py:84-108`
- Test: `tests/core/test_cron_loader.py`

**Step 1: Write the failing test**

Add to `tests/core/test_cron_loader.py` in `TestCronLoader` class:

```python
def test_discover_crons_with_one_off(self, temp_crons_dir):
    """Discover crons includes one_off field."""
    # Create a one-off cron
    cron_dir = temp_crons_dir / "one-off-job"
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
    cron_dir2 = temp_crons_dir / "recurring-job"
    cron_dir2.mkdir()
    (cron_dir2 / "CRON.md").write_text(
        "---\n"
        "name: Recurring Job\n"
        "agent: pickle\n"
        "schedule: '0 * * * *'\n"
        "---\n"
        "Do repeatedly."
    )

    loader = CronLoader(temp_crons_dir)
    defs = loader.discover_crons()

    assert len(defs) == 2
    one_off = next(d for d in defs if d.id == "one-off-job")
    recurring = next(d for d in defs if d.id == "recurring-job")

    assert one_off.one_off is True
    assert recurring.one_off is False
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/core/test_cron_loader.py::TestCronLoader::test_discover_crons_with_one_off -v`
Expected: FAIL (one_off is False for both)

**Step 3: Write minimal implementation**

In `src/picklebot/core/cron_loader.py`, update `_parse_cron_def` method:

```python
def _parse_cron_def(
    self, def_id: str, frontmatter: dict[str, Any], body: str
) -> CronDef | None:
    """Parse cron definition from frontmatter (callback for discover_definitions)."""
    try:
        return CronDef(
            id=def_id,
            name=frontmatter.get("name"),
            agent=frontmatter.get("agent"),
            schedule=frontmatter.get("schedule"),
            prompt=body.strip(),
            one_off=frontmatter.get("one_off", False),
        )
    except ValidationError as e:
        logger.warning(f"Invalid cron '{def_id}': {e}")
        return None
```

Also update `_parse_cron_def_strict` method:

```python
def _parse_cron_def_strict(
    self, def_id: str, frontmatter: dict[str, Any], body: str
) -> CronDef:
    """Parse cron definition with strict validation (raises on error)."""
    try:
        return CronDef(
            id=def_id,
            name=frontmatter.get("name"),
            agent=frontmatter.get("agent"),
            schedule=frontmatter.get("schedule"),
            prompt=body.strip(),
            one_off=frontmatter.get("one_off", False),
        )
    except ValidationError as e:
        raise InvalidDefError("cron", def_id, str(e))
```

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/core/test_cron_loader.py -v`
Expected: All PASS

**Step 5: Commit**

```bash
git add src/picklebot/core/cron_loader.py tests/core/test_cron_loader.py
git commit -m "feat(cron): parse one_off field in CronLoader"
```

---

## Task 3: Update CronExecutor to Delete One-Off Crons

**Files:**
- Modify: `src/picklebot/core/cron_executor.py:1,90-108`
- Test: `tests/core/test_cron_executor.py`

**Step 1: Write the failing test**

Add to `tests/core/test_cron_executor.py`:

```python
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


class TestCronExecutorOneOff:
    """Test one-off cron deletion."""

    @pytest.fixture
    def temp_crons_dir(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    @pytest.mark.asyncio
    async def test_deletes_one_off_cron_after_success(self, temp_crons_dir):
        """One-off cron folder is deleted after successful execution."""
        # Create a one-off cron file
        cron_dir = temp_crons_dir / "one-off-job"
        cron_dir.mkdir()
        (cron_dir / "CRON.md").write_text(
            "---\n"
            "name: One Off\n"
            "agent: pickle\n"
            "schedule: '*/5 * * * *'\n"
            "one_off: true\n"
            "---\n"
            "Do once."
        )

        # Mock the context
        context = MagicMock()
        context.cron_loader.crons_path = temp_crons_dir

        # Mock agent loading and session
        mock_agent_def = MagicMock()
        context.agent_loader.load.return_value = mock_agent_def

        with patch("picklebot.core.cron_executor.Agent") as MockAgent:
            mock_agent = MagicMock()
            mock_session = AsyncMock()
            mock_session.chat = AsyncMock()
            mock_agent.new_session.return_value = mock_session
            MockAgent.return_value = mock_agent

            from picklebot.core.cron_executor import CronExecutor
            from picklebot.core.cron_loader import CronDef

            executor = CronExecutor(context)
            cron_def = CronDef(
                id="one-off-job",
                name="One Off",
                agent="pickle",
                schedule="*/5 * * * *",
                prompt="Do once.",
                one_off=True,
            )

            await executor._run_job(cron_def)

        # Verify cron folder was deleted
        assert not cron_dir.exists()

    @pytest.mark.asyncio
    async def test_keeps_one_off_cron_on_failure(self, temp_crons_dir):
        """One-off cron folder is kept if execution fails."""
        # Create a one-off cron file
        cron_dir = temp_crons_dir / "failing-job"
        cron_dir.mkdir()
        (cron_dir / "CRON.md").write_text(
            "---\n"
            "name: Failing\n"
            "agent: pickle\n"
            "schedule: '*/5 * * * *'\n"
            "one_off: true\n"
            "---\n"
            "Fail."
        )

        # Mock the context
        context = MagicMock()
        context.cron_loader.crons_path = temp_crons_dir

        # Mock agent loading to raise an error
        context.agent_loader.load.side_effect = Exception("Agent not found")

        from picklebot.core.cron_executor import CronExecutor
        from picklebot.core.cron_loader import CronDef

        executor = CronExecutor(context)
        cron_def = CronDef(
            id="failing-job",
            name="Failing",
            agent="pickle",
            schedule="*/5 * * * *",
            prompt="Fail.",
            one_off=True,
        )

        with pytest.raises(Exception, match="Agent not found"):
            await executor._run_job(cron_def)

        # Verify cron folder still exists
        assert cron_dir.exists()

    @pytest.mark.asyncio
    async def test_keeps_recurring_cron_after_success(self, temp_crons_dir):
        """Recurring cron (one_off=False) is not deleted after success."""
        # Create a recurring cron file
        cron_dir = temp_crons_dir / "recurring-job"
        cron_dir.mkdir()
        (cron_dir / "CRON.md").write_text(
            "---\n"
            "name: Recurring\n"
            "agent: pickle\n"
            "schedule: '*/5 * * * *'\n"
            "---\n"
            "Do repeatedly."
        )

        # Mock the context
        context = MagicMock()
        context.cron_loader.crons_path = temp_crons_dir

        # Mock agent loading and session
        mock_agent_def = MagicMock()
        context.agent_loader.load.return_value = mock_agent_def

        with patch("picklebot.core.cron_executor.Agent") as MockAgent:
            mock_agent = MagicMock()
            mock_session = AsyncMock()
            mock_session.chat = AsyncMock()
            mock_agent.new_session.return_value = mock_session
            MockAgent.return_value = mock_agent

            from picklebot.core.cron_executor import CronExecutor
            from picklebot.core.cron_loader import CronDef

            executor = CronExecutor(context)
            cron_def = CronDef(
                id="recurring-job",
                name="Recurring",
                agent="pickle",
                schedule="*/5 * * * *",
                prompt="Do repeatedly.",
                one_off=False,
            )

            await executor._run_job(cron_def)

        # Verify cron folder still exists
        assert cron_dir.exists()
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/core/test_cron_executor.py::TestCronExecutorOneOff -v`
Expected: FAIL (cron folder not deleted)

**Step 3: Write minimal implementation**

In `src/picklebot/core/cron_executor.py`, add import at top:

```python
import shutil
```

Update `_run_job` method:

```python
async def _run_job(self, cron_def: CronDef) -> None:
    """
    Execute a single cron job.

    Args:
        cron_def: Full cron job definition
    """
    try:
        agent_def = self.context.agent_loader.load(cron_def.agent)
        agent = Agent(agent_def, self.context)

        session = agent.new_session()

        await session.chat(cron_def.prompt, SilentFrontend())

        logger.info(f"Cron job {cron_def.id} completed successfully")

        # Delete one-off crons after successful execution
        if cron_def.one_off:
            cron_path = self.context.cron_loader.crons_path / cron_def.id
            shutil.rmtree(cron_path)
            logger.info(f"Deleted one-off cron job: {cron_def.id}")

    except Exception as e:
        logger.error(f"Error executing cron job {cron_def.id}: {e}")
        raise
```

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/core/test_cron_executor.py -v`
Expected: All PASS

**Step 5: Commit**

```bash
git add src/picklebot/core/cron_executor.py tests/core/test_cron_executor.py
git commit -m "feat(cron): delete one-off crons after successful execution"
```

---

## Task 4: Update Cron-Ops Skill

**Files:**
- Modify: `~/.pickle-bot/skills/cron-ops/SKILL.md`

**Step 1: Update validation rules**

Add `one_off` to the Validation Rules section:

```markdown
## Validation Rules

- **Required fields:** `name`, `agent`, `schedule`, and prompt body
- **Schedule:** Valid cron syntax (5 fields), minimum 5-minute granularity
- **Agent:** Must exist in `~/.pickle-bot/agents/`
- **Optional:** `one_off: true` - Job runs once and auto-deletes after success
```

**Step 2: Update create command**

Add clarification step:

```markdown
### create

1. **Clarify with user if not clear:** Should this be a one-off task (`one_off: true`) or recurring?
2. Convert natural language schedule to cron (e.g., "every 30 minutes" → `*/30 * * * *`)
3. Validate schedule:
   ```bash
   uv run python ~/.pickle-bot/skills/cron-ops/scripts/validate_schedule.py "*/15 * * * *"
   ```
4. Verify agent exists: check `~/.pickle-bot/agents/[agent]/AGENT.md`
5. Create the cron:
   ```bash
   uv run python ~/.pickle-bot/skills/cron-ops/scripts/create_cron.py "Name" agent "schedule" "prompt"
   ```
6. Confirm creation to user
```

**Step 3: Add one-off example to Cron File Structure**

Update the example:

```markdown
## Cron File Structure

Crons live in `~/.pickle-bot/crons/[cron-id]/CRON.md`:

```yaml
---
name: Inbox Check
agent: pickle
schedule: "*/15 * * * *"
---

Check my inbox and summarize unread messages.
```

**One-off job (runs once, auto-deletes):**

```yaml
---
name: Birthday Reminder
agent: pickle
schedule: "0 9 15 3 *"
one_off: true
---

Remind me it's Mom's birthday today.
```
```

**Step 4: Commit**

```bash
git add ~/.pickle-bot/skills/cron-ops/SKILL.md
git commit -m "docs(skill): add one_off guidance to cron-ops skill"
```

---

## Task 5: Update CLAUDE.md Documentation

**Files:**
- Modify: `CLAUDE.md`

**Step 1: Update Cron System section**

Find the Cron System section and update to include `one_off`:

```markdown
### Cron System

Cron jobs run scheduled agent invocations. Defined in `~/.pickle-bot/crons/[name]/CRON.md`:

```markdown
---
name: Inbox Check
agent: pickle
schedule: "*/15 * * * *"
one_off: true  # Optional: auto-delete after successful execution
---

Check my inbox and summarize unread messages.
```

Start the server with `picklebot server`. Jobs run sequentially with fresh sessions (no memory between runs).

**One-off jobs:** Set `one_off: true` for tasks that should run once and then auto-delete. The cron file and folder are removed after successful execution. Failed executions keep the file for retry.
```

**Step 2: Commit**

```bash
git add CLAUDE.md
git commit -m "docs: document one_off option in Cron System"
```

---

## Task 6: Run Full Test Suite

**Step 1: Run all tests**

Run: `uv run pytest -v`
Expected: All PASS

**Step 2: Run linting**

Run: `uv run ruff check . && uv run mypy .`
Expected: No errors

**Step 3: Final commit (if any fixes needed)**

```bash
git add -A
git commit -m "fix: address linting issues"
```

---

## Summary

| Task | Description |
|------|-------------|
| 1 | Add `one_off` field to `CronDef` model |
| 2 | Parse `one_off` in `CronLoader` methods |
| 3 | Delete one-off crons in `CronExecutor` after success |
| 4 | Update cron-ops skill with guidance |
| 5 | Update CLAUDE.md documentation |
| 6 | Run full test suite and linting |
