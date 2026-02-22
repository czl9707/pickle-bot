# Onboarding Flow Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add interactive CLI onboarding flow to configure workspace, LLM, and MessageBus for new installations.

**Architecture:** Create `OnboardingWizard` class using `questionary` for interactive prompts. Hook into CLI via new `init` command and auto-detection on missing config. Reuse existing Pydantic models for validation.

**Tech Stack:** Python, Typer, questionary, Pydantic, YAML

---

## Task 1: Add questionary dependency

**Files:**
- Modify: `pyproject.toml`

**Step 1: Add questionary to dependencies**

```toml
# In pyproject.toml, add to dependencies array:
"questionary>=2.0.0",
```

**Step 2: Install dependency**

Run: `uv sync`
Expected: Dependencies resolved and installed

**Step 3: Commit**

```bash
git add pyproject.toml uv.lock
git commit -m "chore: add questionary dependency for onboarding"
```

---

## Task 2: Create OnboardingWizard class skeleton

**Files:**
- Create: `src/picklebot/cli/onboarding.py`
- Create: `tests/cli/test_onboarding.py`

**Step 1: Write the failing test**

```python
# tests/cli/test_onboarding.py
"""Tests for onboarding wizard."""

from picklebot.cli.onboarding import OnboardingWizard


def test_wizard_instantiates():
    """Test that OnboardingWizard can be instantiated."""
    wizard = OnboardingWizard()
    assert wizard.state == {}
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/cli/test_onboarding.py -v`
Expected: FAIL with "No module named 'picklebot.cli.onboarding'"

**Step 3: Write minimal implementation**

```python
# src/picklebot/cli/onboarding.py
"""Interactive onboarding wizard for pickle-bot."""

from pathlib import Path


class OnboardingWizard:
    """Guides users through initial configuration."""

    def __init__(self, workspace: Path | None = None):
        """
        Initialize the wizard.

        Args:
            workspace: Path to workspace directory. Defaults to ~/.pickle-bot/
        """
        self.workspace = workspace or Path.home() / ".pickle-bot"
        self.state: dict = {}
```

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/cli/test_onboarding.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/picklebot/cli/onboarding.py tests/cli/test_onboarding.py
git commit -m "feat: add OnboardingWizard class skeleton"
```

---

## Task 3: Implement workspace setup step

**Files:**
- Modify: `src/picklebot/cli/onboarding.py`
- Modify: `tests/cli/test_onboarding.py`

**Step 1: Write the failing test**

```python
# Add to tests/cli/test_onboarding.py
import tempfile
from pathlib import Path


def test_setup_workspace_creates_directories():
    """Test that setup_workspace creates all required directories."""
    with tempfile.TemporaryDirectory() as tmpdir:
        workspace = Path(tmpdir) / "test-workspace"
        wizard = OnboardingWizard(workspace=workspace)
        wizard.setup_workspace()

        assert workspace.exists()
        assert (workspace / "agents").exists()
        assert (workspace / "skills").exists()
        assert (workspace / "crons").exists()
        assert (workspace / "memories").exists()
        assert (workspace / ".history").exists()
        assert (workspace / ".logs").exists()
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/cli/test_onboarding.py::test_setup_workspace_creates_directories -v`
Expected: FAIL with "'OnboardingWizard' object has no attribute 'setup_workspace'"

**Step 3: Write minimal implementation**

```python
# Add method to OnboardingWizard class in src/picklebot/cli/onboarding.py

    def setup_workspace(self) -> None:
        """Create workspace directory and required subdirectories."""
        self.workspace.mkdir(parents=True, exist_ok=True)

        subdirs = ["agents", "skills", "crons", "memories", ".history", ".logs"]
        for subdir in subdirs:
            (self.workspace / subdir).mkdir(exist_ok=True)
```

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/cli/test_onboarding.py::test_setup_workspace_creates_directories -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/picklebot/cli/onboarding.py tests/cli/test_onboarding.py
git commit -m "feat: add workspace setup to OnboardingWizard"
```

---

## Task 4: Implement LLM configuration step

**Files:**
- Modify: `src/picklebot/cli/onboarding.py`
- Modify: `tests/cli/test_onboarding.py`

**Step 1: Write the failing test**

```python
# Add to tests/cli/test_onboarding.py
from unittest.mock import patch, MagicMock


def test_configure_llm_stores_state():
    """Test that configure_llm stores LLM config in state."""
    wizard = OnboardingWizard()

    with patch("questionary.select") as mock_select, \
         patch("questionary.text") as mock_text:
        mock_select.return_value.ask.return_value = "openai"
        mock_text.return_value.ask.side_effect = ["gpt-4", "sk-test-key", ""]

        wizard.configure_llm()

    assert wizard.state["llm"]["provider"] == "openai"
    assert wizard.state["llm"]["model"] == "gpt-4"
    assert wizard.state["llm"]["api_key"] == "sk-test-key"
    assert wizard.state["llm"].get("api_base") is None
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/cli/test_onboarding.py::test_configure_llm_stores_state -v`
Expected: FAIL with "'OnboardingWizard' object has no attribute 'configure_llm'"

**Step 3: Write minimal implementation**

```python
# Add import at top of src/picklebot/cli/onboarding.py
import questionary

# Add method to OnboardingWizard class

    def configure_llm(self) -> None:
        """Prompt user for LLM configuration."""
        provider = questionary.select(
            "Select LLM provider:",
            choices=["openai", "anthropic", "zai", "other"],
        ).ask()

        if provider == "other":
            provider = questionary.text("Enter provider name:").ask()

        model = questionary.text(
            "Model name:",
            default="gpt-4" if provider == "openai" else "claude-3-opus",
        ).ask()

        api_key = questionary.text("API key:").ask()

        api_base = questionary.text(
            "API base URL (optional, press Enter to skip):",
            default="",
        ).ask()

        self.state["llm"] = {
            "provider": provider,
            "model": model,
            "api_key": api_key,
        }

        if api_base:
            self.state["llm"]["api_base"] = api_base
```

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/cli/test_onboarding.py::test_configure_llm_stores_state -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/picklebot/cli/onboarding.py tests/cli/test_onboarding.py
git commit -m "feat: add LLM configuration step to OnboardingWizard"
```

---

## Task 5: Implement MessageBus configuration step

**Files:**
- Modify: `src/picklebot/cli/onboarding.py`
- Modify: `tests/cli/test_onboarding.py`

**Step 1: Write the failing test**

```python
# Add to tests/cli/test_onboarding.py


def test_configure_messagebus_stores_state():
    """Test that configure_messagebus stores MessageBus config in state."""
    wizard = OnboardingWizard()

    with patch("questionary.checkbox") as mock_checkbox, \
         patch("questionary.text") as mock_text, \
         patch("questionary.confirm") as mock_confirm:
        # Select telegram only
        mock_checkbox.return_value.ask.return_value = ["telegram"]
        mock_text.return_value.ask.side_effect = [
            "123:ABC",  # telegram bot token
            "12345",    # telegram allowed user ids
            "12345",    # telegram default chat id
        ]

        wizard.configure_messagebus()

    assert wizard.state["messagebus"]["enabled"] is True
    assert wizard.state["messagebus"]["default_platform"] == "telegram"
    assert wizard.state["messagebus"]["telegram"]["bot_token"] == "123:ABC"


def test_configure_messagebus_skip_all():
    """Test that selecting no platforms results in disabled messagebus."""
    wizard = OnboardingWizard()

    with patch("questionary.checkbox") as mock_checkbox:
        mock_checkbox.return_value.ask.return_value = []

        wizard.configure_messagebus()

    assert wizard.state["messagebus"]["enabled"] is False
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/cli/test_onboarding.py::test_configure_messagebus_stores_state -v`
Expected: FAIL with "'OnboardingWizard' object has no attribute 'configure_messagebus'"

**Step 3: Write minimal implementation**

```python
# Add method to OnboardingWizard class in src/picklebot/cli/onboarding.py

    def configure_messagebus(self) -> None:
        """Prompt user for MessageBus configuration."""
        platforms = questionary.checkbox(
            "Select messaging platforms to enable:",
            choices=["telegram", "discord"],
        ).ask()

        if not platforms:
            self.state["messagebus"] = {"enabled": False}
            return

        self.state["messagebus"] = {
            "enabled": True,
            "default_platform": platforms[0],
        }

        if "telegram" in platforms:
            self.state["messagebus"]["telegram"] = self._configure_telegram()

        if "discord" in platforms:
            self.state["messagebus"]["discord"] = self._configure_discord()

    def _configure_telegram(self) -> dict:
        """Prompt for Telegram-specific configuration."""
        bot_token = questionary.text("Telegram bot token:").ask()

        allowed_users = questionary.text(
            "Allowed user IDs (comma-separated, or press Enter for open access):",
            default="",
        ).ask()

        default_chat = questionary.text(
            "Default chat ID (optional, press Enter to skip):",
            default="",
        ).ask()

        config: dict = {
            "enabled": True,
            "bot_token": bot_token,
            "allowed_user_ids": [],
        }

        if allowed_users:
            config["allowed_user_ids"] = [
                uid.strip() for uid in allowed_users.split(",") if uid.strip()
            ]

        if default_chat:
            config["default_chat_id"] = default_chat

        return config

    def _configure_discord(self) -> dict:
        """Prompt for Discord-specific configuration."""
        bot_token = questionary.text("Discord bot token:").ask()

        channel_id = questionary.text(
            "Channel ID to listen on (optional, press Enter for all channels):",
            default="",
        ).ask()

        allowed_users = questionary.text(
            "Allowed user IDs (comma-separated, or press Enter for open access):",
            default="",
        ).ask()

        default_chat = questionary.text(
            "Default channel ID for proactive posts (optional):",
            default="",
        ).ask()

        config: dict = {
            "enabled": True,
            "bot_token": bot_token,
            "allowed_user_ids": [],
        }

        if channel_id:
            config["channel_id"] = channel_id

        if allowed_users:
            config["allowed_user_ids"] = [
                uid.strip() for uid in allowed_users.split(",") if uid.strip()
            ]

        if default_chat:
            config["default_chat_id"] = default_chat

        return config
```

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/cli/test_onboarding.py::test_configure_messagebus_stores_state tests/cli/test_onboarding.py::test_configure_messagebus_skip_all -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/picklebot/cli/onboarding.py tests/cli/test_onboarding.py
git commit -m "feat: add MessageBus configuration step to OnboardingWizard"
```

---

## Task 6: Implement save_config method

**Files:**
- Modify: `src/picklebot/cli/onboarding.py`
- Modify: `tests/cli/test_onboarding.py`

**Step 1: Write the failing test**

```python
# Add to tests/cli/test_onboarding.py
import yaml


def test_save_config_writes_yaml():
    """Test that save_config writes valid YAML files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        workspace = Path(tmpdir) / "test-workspace"
        wizard = OnboardingWizard(workspace=workspace)

        wizard.state = {
            "llm": {"provider": "openai", "model": "gpt-4", "api_key": "test"},
            "messagebus": {"enabled": False},
        }

        wizard.save_config()

        user_config_path = workspace / "config.user.yaml"
        assert user_config_path.exists()

        with open(user_config_path) as f:
            config = yaml.safe_load(f)

        assert config["llm"]["provider"] == "openai"
        assert config["messagebus"]["enabled"] is False


def test_save_config_creates_system_defaults():
    """Test that save_config creates config.system.yaml with defaults."""
    with tempfile.TemporaryDirectory() as tmpdir:
        workspace = Path(tmpdir) / "test-workspace"
        wizard = OnboardingWizard(workspace=workspace)

        wizard.state = {
            "llm": {"provider": "openai", "model": "gpt-4", "api_key": "test"},
            "messagebus": {"enabled": False},
        }

        wizard.save_config()

        system_config_path = workspace / "config.system.yaml"
        assert system_config_path.exists()

        with open(system_config_path) as f:
            config = yaml.safe_load(f)

        assert "default_agent" in config
        assert "logging_path" in config
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/cli/test_onboarding.py::test_save_config_writes_yaml -v`
Expected: FAIL with "'OnboardingWizard' object has no attribute 'save_config'"

**Step 3: Write minimal implementation**

```python
# Add import at top of src/picklebot/cli/onboarding.py
import yaml

# Add method to OnboardingWizard class

    def save_config(self) -> None:
        """Write configuration to YAML files."""
        # Ensure workspace exists
        self.workspace.mkdir(parents=True, exist_ok=True)

        # Write system defaults (only if not exists)
        system_config_path = self.workspace / "config.system.yaml"
        if not system_config_path.exists():
            system_defaults = {
                "default_agent": "pickle",
                "logging_path": ".logs",
                "history_path": ".history",
            }
            with open(system_config_path, "w") as f:
                yaml.dump(system_defaults, f, default_flow_style=False)

        # Write user config
        user_config_path = self.workspace / "config.user.yaml"
        with open(user_config_path, "w") as f:
            yaml.dump(self.state, f, default_flow_style=False)
```

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/cli/test_onboarding.py::test_save_config_writes_yaml tests/cli/test_onboarding.py::test_save_config_creates_system_defaults -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/picklebot/cli/onboarding.py tests/cli/test_onboarding.py
git commit -m "feat: add save_config method to OnboardingWizard"
```

---

## Task 7: Implement run method (main entry point)

**Files:**
- Modify: `src/picklebot/cli/onboarding.py`
- Modify: `tests/cli/test_onboarding.py`

**Step 1: Write the failing test**

```python
# Add to tests/cli/test_onboarding.py


def test_run_orchestrates_all_steps():
    """Test that run() calls all steps in order."""
    with tempfile.TemporaryDirectory() as tmpdir:
        workspace = Path(tmpdir) / "test-workspace"
        wizard = OnboardingWizard(workspace=workspace)

        with patch.object(wizard, "setup_workspace") as mock_setup, \
             patch.object(wizard, "configure_llm") as mock_llm, \
             patch.object(wizard, "configure_messagebus") as mock_bus, \
             patch.object(wizard, "save_config") as mock_save:
            wizard.run()

        mock_setup.assert_called_once()
        mock_llm.assert_called_once()
        mock_bus.assert_called_once()
        mock_save.assert_called_once()
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/cli/test_onboarding.py::test_run_orchestrates_all_steps -v`
Expected: FAIL with "'OnboardingWizard' object has no attribute 'run'"

**Step 3: Write minimal implementation**

```python
# Add import at top of src/picklebot/cli/onboarding.py
from rich.console import Console

# Add method to OnboardingWizard class

    def run(self) -> None:
        """Run the complete onboarding flow."""
        console = Console()

        console.print("\n[bold cyan]Welcome to Pickle-Bot![/bold cyan]")
        console.print("Let's set up your configuration.\n")

        self.setup_workspace()
        self.configure_llm()
        self.configure_messagebus()
        self.save_config()

        console.print("\n[green]Configuration saved![/green]")
        console.print(f"Config file: {self.workspace / 'config.user.yaml'}")
        console.print("Edit this file to make changes.\n")
```

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/cli/test_onboarding.py::test_run_orchestrates_all_steps -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/picklebot/cli/onboarding.py tests/cli/test_onboarding.py
git commit -m "feat: add run method to OnboardingWizard"
```

---

## Task 8: Add `init` CLI command

**Files:**
- Modify: `src/picklebot/cli/main.py`
- Modify: `tests/cli/test_main.py`

**Step 1: Write the failing test**

```python
# Add to tests/cli/test_main.py (create if doesn't exist)
"""Tests for CLI main module."""

from click.testing import CliRunner
from picklebot.cli.main import app


def test_init_command_exists():
    """Test that init command is registered."""
    runner = CliRunner()
    result = runner.invoke(app, ["init", "--help"])
    assert result.exit_code == 0
    assert "Initialize" in result.output.lower() or "onboarding" in result.output.lower()
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/cli/test_main.py::test_init_command_exists -v`
Expected: FAIL with "No such command: init"

**Step 3: Write minimal implementation**

```python
# Add to src/picklebot/cli/main.py

from pathlib import Path
from picklebot.cli.onboarding import OnboardingWizard

# Add new command after the server command

@app.command()
def init(
    ctx: typer.Context,
) -> None:
    """Initialize pickle-bot configuration with interactive onboarding."""
    workspace = ctx.obj.get("config").workspace if ctx.obj else Path.home() / ".pickle-bot"
    wizard = OnboardingWizard(workspace=workspace)
    wizard.run()
```

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/cli/test_main.py::test_init_command_exists -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/picklebot/cli/main.py tests/cli/test_main.py
git commit -m "feat: add init CLI command for onboarding"
```

---

## Task 9: Add auto-detection for missing config

**Files:**
- Modify: `src/picklebot/cli/main.py`
- Modify: `tests/cli/test_main.py`

**Step 1: Write the failing test**

```python
# Add to tests/cli/test_main.py
import tempfile
from unittest.mock import patch


def test_auto_onboarding_when_config_missing():
    """Test that onboarding is offered when config is missing."""
    runner = CliRunner()

    with tempfile.TemporaryDirectory() as tmpdir:
        workspace = Path(tmpdir) / "no-config"

        with patch("questionary.confirm") as mock_confirm:
            mock_confirm.return_value.ask.return_value = False
            result = runner.invoke(app, ["--workspace", str(workspace), "chat"])

        # Should exit gracefully after user declines onboarding
        assert result.exit_code != 0
        assert "config" in result.output.lower() or "init" in result.output.lower()
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/cli/test_main.py::test_auto_onboarding_when_config_missing -v`
Expected: FAIL (current behavior exits immediately without offering onboarding)

**Step 3: Write minimal implementation**

```python
# Modify src/picklebot/cli/main.py
# Update load_config_callback function

import questionary
from picklebot.cli.onboarding import OnboardingWizard

def load_config_callback(ctx: typer.Context, workspace: str):
    """Load configuration and store it in the context."""
    workspace_path = Path(workspace)
    config_file = workspace_path / "config.user.yaml"

    try:
        if not config_file.exists():
            # Offer onboarding
            run_onboarding = questionary.confirm(
                "No configuration found. Run onboarding now?",
                default=True,
            ).ask()

            if run_onboarding:
                wizard = OnboardingWizard(workspace=workspace_path)
                wizard.run()
            else:
                console.print(
                    "[yellow]Run 'picklebot init' to set up configuration.[/yellow]"
                )
                raise typer.Exit(1)

        cfg = Config.load(workspace_path)
        ctx.ensure_object(dict)
        ctx.obj["config"] = cfg

    except FileNotFoundError as e:
        console.print(f"[red]{e}[/red]")
        raise typer.Exit(1)
    except Exception as e:
        console.print(f"[red]Error loading config: {e}[/red]")
        raise typer.Exit(1)
```

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/cli/test_main.py::test_auto_onboarding_when_config_missing -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/picklebot/cli/main.py tests/cli/test_main.py
git commit -m "feat: add auto-detection for missing config with onboarding prompt"
```

---

## Task 10: Add validation before saving config

**Files:**
- Modify: `src/picklebot/cli/onboarding.py`
- Modify: `tests/cli/test_onboarding.py`

**Step 1: Write the failing test**

```python
# Add to tests/cli/test_onboarding.py


def test_save_config_validates_with_pydantic():
    """Test that save_config validates config structure."""
    with tempfile.TemporaryDirectory() as tmpdir:
        workspace = Path(tmpdir) / "test-workspace"
        wizard = OnboardingWizard(workspace=workspace)

        # Missing required fields
        wizard.state = {
            "llm": {"provider": "openai"},  # missing model and api_key
            "messagebus": {"enabled": False},
        }

        with patch("questionary.confirm") as mock_confirm:
            mock_confirm.return_value.ask.return_value = False
            result = wizard.save_config()

        # Should handle validation error gracefully
        assert result is False or "error" in str(result).lower()
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/cli/test_onboarding.py::test_save_config_validates_with_pydantic -v`
Expected: FAIL (currently no validation)

**Step 3: Write minimal implementation**

```python
# Modify save_config method in src/picklebot/cli/onboarding.py

# Add import
from picklebot.utils.config import Config
from pydantic import ValidationError

    def save_config(self) -> bool:
        """
        Write configuration to YAML files.

        Returns:
            True if save succeeded, False if validation failed.
        """
        # Validate config structure
        try:
            config_data = {"workspace": self.workspace}
            config_data.update(self.state)
            Config.model_validate(config_data)
        except ValidationError as e:
            console = Console()
            console.print(f"\n[red]Configuration validation failed:[/red]")
            for error in e.errors():
                console.print(f"  - {error['loc'][0]}: {error['msg']}")
            return False

        # Ensure workspace exists
        self.workspace.mkdir(parents=True, exist_ok=True)

        # Write system defaults (only if not exists)
        system_config_path = self.workspace / "config.system.yaml"
        if not system_config_path.exists():
            system_defaults = {
                "default_agent": "pickle",
                "logging_path": ".logs",
                "history_path": ".history",
            }
            with open(system_config_path, "w") as f:
                yaml.dump(system_defaults, f, default_flow_style=False)

        # Write user config
        user_config_path = self.workspace / "config.user.yaml"
        with open(user_config_path, "w") as f:
            yaml.dump(self.state, f, default_flow_style=False)

        return True
```

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/cli/test_onboarding.py::test_save_config_validates_with_pydantic -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/picklebot/cli/onboarding.py tests/cli/test_onboarding.py
git commit -m "feat: add Pydantic validation before saving config"
```

---

## Task 11: Run full test suite and linting

**Step 1: Run all tests**

Run: `uv run pytest tests/cli/ -v`
Expected: All tests pass

**Step 2: Run linting and formatting**

Run: `uv run black . && uv run ruff check .`
Expected: No errors

**Step 3: Fix any issues and commit**

```bash
git add .
git commit -m "fix: address linting issues"
```

---

## Task 12: Manual integration test

**Step 1: Test init command**

Run: `uv run picklebot init --help`
Expected: Shows help text

**Step 2: Test full onboarding (optional, requires terminal interaction)**

Run: `uv run picklebot init`
Expected: Interactive prompts appear, config is saved

**Step 3: Final commit**

```bash
git add .
git commit -m "chore: verify onboarding flow works end-to-end"
```
