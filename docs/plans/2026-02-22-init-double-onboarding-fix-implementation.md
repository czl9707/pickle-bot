# Fix Init Double Onboarding Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Fix the double onboarding bug by making `init` command skip config callback and removing inline onboarding offer from callback.

**Architecture:** Modify `load_config_callback` to detect `init` command and skip config check. Remove inline onboarding offer - just exit with instructions when config is missing.

**Tech Stack:** Python, Typer CLI, pytest

---

### Task 1: Update Tests for New Behavior

**Files:**
- Modify: `tests/cli/test_main.py:23-45`

**Step 1: Write the failing test**

Replace `test_auto_onboarding_when_config_missing` with new tests for the updated behavior:

```python
def test_no_config_shows_init_instructions():
    """Test that missing config shows instructions to run init."""
    runner = CliRunner()

    with tempfile.TemporaryDirectory() as tmpdir:
        workspace = Path(tmpdir) / "no-config"

        result = runner.invoke(app, ["--workspace", str(workspace), "chat"])

        # Should exit with error
        assert result.exit_code == 1
        # Should show instructions to run init
        assert "picklebot init" in result.output.lower()


def test_init_skips_config_check():
    """Test that init command works without existing config."""
    runner = CliRunner()

    with tempfile.TemporaryDirectory() as tmpdir:
        workspace = Path(tmpdir) / "no-config"

        with patch("picklebot.cli.onboarding.OnboardingWizard.run") as mock_run:
            result = runner.invoke(app, ["--workspace", str(workspace), "init"])

        # Should call wizard exactly once
        mock_run.assert_called_once()
        # Should exit successfully
        assert result.exit_code == 0
```

**Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/cli/test_main.py -v`
Expected: Both new tests FAIL

**Step 3: Commit**

```bash
git add tests/cli/test_main.py
git commit -m "test: update tests for init command fix"
```

---

### Task 2: Update load_config_callback

**Files:**
- Modify: `src/picklebot/cli/main.py:26-57`

**Step 1: Write the implementation**

Replace the `load_config_callback` function:

```python
def load_config_callback(ctx: typer.Context, workspace: str):
    """Load configuration and store it in the context."""
    workspace_path = Path(workspace)

    # Skip config check for init command - it handles its own setup
    if ctx.invoked_subcommand == "init":
        ctx.ensure_object(dict)
        ctx.obj["workspace"] = workspace_path
        return

    config_file = workspace_path / "config.user.yaml"

    if not config_file.exists():
        console.print("[yellow]No configuration found.[/yellow]")
        console.print("Run [bold]picklebot init[/bold] to set up.")
        raise typer.Exit(1)

    try:
        cfg = Config.load(workspace_path)
        ctx.ensure_object(dict)
        ctx.obj["config"] = cfg
    except Exception as e:
        console.print(f"[red]Error loading config: {e}[/red]")
        raise typer.Exit(1)
```

**Step 2: Remove unused import**

Remove the `questionary` import from line 6:

```python
import typer
```

(Delete the `import questionary` line)

**Step 3: Run tests to verify they pass**

Run: `uv run pytest tests/cli/test_main.py -v`
Expected: All tests PASS

**Step 4: Commit**

```bash
git add src/picklebot/cli/main.py
git commit -m "fix: skip config callback for init command"
```

---

### Task 3: Update init Command

**Files:**
- Modify: `src/picklebot/cli/main.py:105-114`

**Step 1: Update the init command**

Replace the `init` function:

```python
@app.command()
def init(ctx: typer.Context) -> None:
    """Initialize pickle-bot configuration with interactive onboarding."""
    workspace = ctx.obj.get("workspace", Path.home() / ".pickle-bot")
    wizard = OnboardingWizard(workspace=workspace)
    wizard.run()
```

**Step 2: Run tests to verify they still pass**

Run: `uv run pytest tests/cli/test_main.py -v`
Expected: All tests PASS

**Step 3: Commit**

```bash
git add src/picklebot/cli/main.py
git commit -m "fix: use workspace from context in init command"
```

---

### Task 4: Run Full Test Suite

**Step 1: Run all tests**

Run: `uv run pytest -v`
Expected: All tests PASS

**Step 2: Run linter**

Run: `uv run black . && uv run ruff check .`
Expected: No errors

**Step 3: Final commit if any formatting changes**

```bash
git add -A
git commit -m "style: format code" || echo "No formatting changes needed"
```
