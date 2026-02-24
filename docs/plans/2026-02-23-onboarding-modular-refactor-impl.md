# Onboarding Modular Refactor Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Refactor OnboardingWizard into modular step classes for testability, extensibility, and readability.

**Architecture:** Extract step logic into individual classes inheriting from BaseStep. Wizard becomes a thin orchestrator iterating through a STEPS list. State dict passed explicitly between steps.

**Tech Stack:** Python 3.13, questionary, rich, pytest

---

## Task 1: Create onboarding package structure

**Files:**
- Create: `src/picklebot/cli/onboarding/__init__.py`
- Create: `src/picklebot/cli/onboarding/steps.py`
- Create: `src/picklebot/cli/onboarding/wizard.py`

**Step 1: Create package directory**

```bash
mkdir -p src/picklebot/cli/onboarding
```

**Step 2: Create __init__.py with exports**

```python
# src/picklebot/cli/onboarding/__init__.py
"""Onboarding wizard package."""

from picklebot.cli.onboarding.wizard import OnboardingWizard

__all__ = ["OnboardingWizard"]
```

**Step 3: Create empty steps.py placeholder**

```python
# src/picklebot/cli/onboarding/steps.py
"""Onboarding step classes."""

from pathlib import Path

from rich.console import Console


class BaseStep:
    """Base class for onboarding steps."""

    def __init__(self, workspace: Path, console: Console, defaults: Path):
        self.workspace = workspace
        self.console = console
        self.defaults = defaults

    def run(self, state: dict) -> bool:
        """Execute step. Return True on success, False to abort."""
        raise NotImplementedError
```

**Step 4: Create empty wizard.py placeholder**

```python
# src/picklebot/cli/onboarding/wizard.py
"""Onboarding wizard orchestrator."""

from pathlib import Path

from picklebot.cli.onboarding.steps import BaseStep


class OnboardingWizard:
    """Guides users through initial configuration."""

    DEFAULT_WORKSPACE = (
        Path(__file__).parent.parent.parent.parent / "default_workspace"
    )

    STEPS: list[type[BaseStep]] = []

    def __init__(self, workspace: Path | None = None):
        self.workspace = workspace or Path.home() / ".pickle-bot"

    def run(self) -> bool:
        """Run all onboarding steps. Returns True if successful."""
        raise NotImplementedError
```

**Step 5: Commit**

```bash
git add src/picklebot/cli/onboarding/
git commit -m "feat(onboarding): create package structure with BaseStep"
```

---

## Task 2: Create tests directory structure

**Files:**
- Create: `tests/cli/onboarding/__init__.py`
- Create: `tests/cli/onboarding/test_steps.py`
- Create: `tests/cli/onboarding/test_wizard.py`

**Step 1: Create tests directory**

```bash
mkdir -p tests/cli/onboarding
```

**Step 2: Create __init__.py**

```python
# tests/cli/onboarding/__init__.py
```

**Step 3: Create test_steps.py with base tests**

```python
# tests/cli/onboarding/test_steps.py
"""Unit tests for onboarding step classes."""

from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest
from rich.console import Console

from picklebot.cli.onboarding.steps import (
    BaseStep,
    CheckWorkspaceStep,
    SetupWorkspaceStep,
    ConfigureLLMStep,
    ConfigureExtraFunctionalityStep,
    CopyDefaultAssetsStep,
    ConfigureMessageBusStep,
    SaveConfigStep,
)


class TestBaseStep:
    """Tests for BaseStep."""

    def test_init_stores_dependencies(self, tmp_path: Path):
        """BaseStep stores workspace, console, and defaults."""
        console = Console()
        defaults = tmp_path / "defaults"

        step = BaseStep(tmp_path, console, defaults)

        assert step.workspace == tmp_path
        assert step.console is console
        assert step.defaults == defaults

    def test_run_raises_not_implemented(self, tmp_path: Path):
        """BaseStep.run raises NotImplementedError."""
        console = Console()
        defaults = tmp_path / "defaults"
        step = BaseStep(tmp_path, console, defaults)

        with pytest.raises(NotImplementedError):
            step.run({})


class TestSetupWorkspaceStep:
    """Tests for SetupWorkspaceStep."""

    def test_creates_all_directories(self, tmp_path: Path):
        """SetupWorkspaceStep creates all required directories."""
        console = Console()
        defaults = tmp_path / "defaults"
        workspace = tmp_path / "workspace"
        step = SetupWorkspaceStep(workspace, console, defaults)

        result = step.run({})

        assert result is True
        assert workspace.exists()
        assert (workspace / "agents").exists()
        assert (workspace / "skills").exists()
        assert (workspace / "crons").exists()
        assert (workspace / "memories").exists()
        assert (workspace / ".history").exists()
        assert (workspace / ".logs").exists()

    def test_idempotent(self, tmp_path: Path):
        """SetupWorkspaceStep can be run multiple times safely."""
        console = Console()
        defaults = tmp_path / "defaults"
        workspace = tmp_path / "workspace"
        step = SetupWorkspaceStep(workspace, console, defaults)

        step.run({})
        result = step.run({})

        assert result is True


class TestCheckWorkspaceStep:
    """Tests for CheckWorkspaceStep."""

    def test_returns_true_when_no_config(self, tmp_path: Path):
        """Returns True when config.user.yaml doesn't exist."""
        console = Console()
        defaults = tmp_path / "defaults"
        workspace = tmp_path / "workspace"
        step = CheckWorkspaceStep(workspace, console, defaults)

        result = step.run({})

        assert result is True

    def test_prompts_when_config_exists(self, tmp_path: Path):
        """Prompts user when config.user.yaml exists."""
        console = Console()
        defaults = tmp_path / "defaults"
        workspace = tmp_path / "workspace"
        workspace.mkdir()
        (workspace / "config.user.yaml").write_text("llm: {}")
        step = CheckWorkspaceStep(workspace, console, defaults)

        with patch("questionary.confirm") as mock_confirm:
            mock_confirm.return_value.ask.return_value = True
            result = step.run({})

        mock_confirm.assert_called_once()
        assert result is True

    def test_returns_false_when_user_declines(self, tmp_path: Path):
        """Returns False when user declines overwrite."""
        console = Console()
        defaults = tmp_path / "defaults"
        workspace = tmp_path / "workspace"
        workspace.mkdir()
        (workspace / "config.user.yaml").write_text("llm: {}")
        step = CheckWorkspaceStep(workspace, console, defaults)

        with patch("questionary.confirm") as mock_confirm:
            mock_confirm.return_value.ask.return_value = False
            result = step.run({})

        assert result is False


class TestConfigureLLMStep:
    """Tests for ConfigureLLMStep."""

    def test_stores_llm_config_in_state(self, tmp_path: Path):
        """ConfigureLLMStep stores LLM config in state."""
        console = Console()
        defaults = tmp_path / "defaults"
        step = ConfigureLLMStep(tmp_path, console, defaults)

        with (
            patch("questionary.select") as mock_select,
            patch("questionary.text") as mock_text,
        ):
            mock_select.return_value.ask.return_value = "openai"
            mock_text.return_value.ask.side_effect = ["gpt-4o", "sk-test", ""]

            state = {}
            result = step.run(state)

        assert result is True
        assert state["llm"]["provider"] == "openai"
        assert state["llm"]["model"] == "gpt-4o"
        assert state["llm"]["api_key"] == "sk-test"
        assert "api_base" not in state["llm"]

    def test_includes_api_base_when_provided(self, tmp_path: Path):
        """ConfigureLLMStep includes api_base when user provides one."""
        console = Console()
        defaults = tmp_path / "defaults"
        step = ConfigureLLMStep(tmp_path, console, defaults)

        with (
            patch("questionary.select") as mock_select,
            patch("questionary.text") as mock_text,
        ):
            mock_select.return_value.ask.return_value = "other"
            mock_text.return_value.ask.side_effect = [
                "llama-3",
                "my-key",
                "http://localhost:11434",
            ]

            state = {}
            result = step.run(state)

        assert result is True
        assert state["llm"]["api_base"] == "http://localhost:11434"


class TestConfigureExtraFunctionalityStep:
    """Tests for ConfigureExtraFunctionalityStep."""

    def test_no_selection_no_state(self, tmp_path: Path):
        """No selection results in no state changes."""
        console = Console()
        defaults = tmp_path / "defaults"
        step = ConfigureExtraFunctionalityStep(tmp_path, console, defaults)

        with patch("questionary.checkbox") as mock_checkbox:
            mock_checkbox.return_value.ask.return_value = []

            state = {}
            result = step.run(state)

        assert result is True
        assert "websearch" not in state
        assert "webread" not in state
        assert "api" not in state

    def test_websearch_with_api_key(self, tmp_path: Path):
        """Websearch selection with API key stores config."""
        console = Console()
        defaults = tmp_path / "defaults"
        step = ConfigureExtraFunctionalityStep(tmp_path, console, defaults)

        with (
            patch("questionary.checkbox") as mock_checkbox,
            patch("questionary.text") as mock_text,
        ):
            mock_checkbox.return_value.ask.return_value = ["websearch"]
            mock_text.return_value.ask.return_value = "test-api-key"

            state = {}
            result = step.run(state)

        assert result is True
        assert state["websearch"] == {"provider": "brave", "api_key": "test-api-key"}

    def test_websearch_empty_key_skips(self, tmp_path: Path, capsys):
        """Websearch with empty API key skips config."""
        console = Console()
        defaults = tmp_path / "defaults"
        step = ConfigureExtraFunctionalityStep(tmp_path, console, defaults)

        with (
            patch("questionary.checkbox") as mock_checkbox,
            patch("questionary.text") as mock_text,
        ):
            mock_checkbox.return_value.ask.return_value = ["websearch"]
            mock_text.return_value.ask.return_value = ""

            state = {}
            result = step.run(state)

        assert result is True
        assert "websearch" not in state

    def test_webread_selection(self, tmp_path: Path):
        """Webread selection stores config."""
        console = Console()
        defaults = tmp_path / "defaults"
        step = ConfigureExtraFunctionalityStep(tmp_path, console, defaults)

        with patch("questionary.checkbox") as mock_checkbox:
            mock_checkbox.return_value.ask.return_value = ["webread"]

            state = {}
            result = step.run(state)

        assert result is True
        assert state["webread"] == {"provider": "crawl4ai"}

    def test_api_selection(self, tmp_path: Path):
        """API selection stores enabled config."""
        console = Console()
        defaults = tmp_path / "defaults"
        step = ConfigureExtraFunctionalityStep(tmp_path, console, defaults)

        with patch("questionary.checkbox") as mock_checkbox:
            mock_checkbox.return_value.ask.return_value = ["api"]

            state = {}
            result = step.run(state)

        assert result is True
        assert state["api"] == {"enabled": True}

    def test_all_selections(self, tmp_path: Path):
        """All features can be selected together."""
        console = Console()
        defaults = tmp_path / "defaults"
        step = ConfigureExtraFunctionalityStep(tmp_path, console, defaults)

        with (
            patch("questionary.checkbox") as mock_checkbox,
            patch("questionary.text") as mock_text,
        ):
            mock_checkbox.return_value.ask.return_value = [
                "websearch",
                "webread",
                "api",
            ]
            mock_text.return_value.ask.return_value = "test-key"

            state = {}
            result = step.run(state)

        assert result is True
        assert "websearch" in state
        assert "webread" in state
        assert "api" in state


class TestCopyDefaultAssetsStep:
    """Tests for CopyDefaultAssetsStep."""

    def test_skips_when_no_defaults(self, tmp_path: Path):
        """Does nothing when defaults directory doesn't exist."""
        console = Console()
        defaults = tmp_path / "nonexistent"
        workspace = tmp_path / "workspace"
        workspace.mkdir()
        (workspace / "agents").mkdir()
        (workspace / "skills").mkdir()
        step = CopyDefaultAssetsStep(workspace, console, defaults)

        with patch("questionary.checkbox") as mock_checkbox:
            result = step.run({})

        mock_checkbox.assert_not_called()
        assert result is True

    def test_copies_selected_assets(self, tmp_path: Path):
        """Copies selected agents and skills to workspace."""
        console = Console()
        defaults = tmp_path / "defaults"
        workspace = tmp_path / "workspace"
        workspace.mkdir()
        (workspace / "agents").mkdir()
        (workspace / "skills").mkdir()

        # Create mock default agent
        mock_agent = defaults / "agents" / "pickle"
        mock_agent.mkdir(parents=True)
        (mock_agent / "AGENT.md").write_text("# Pickle Agent")

        step = CopyDefaultAssetsStep(workspace, console, defaults)

        with patch("questionary.checkbox") as mock_checkbox:
            mock_checkbox.return_value.ask.side_effect = [["pickle"], []]
            result = step.run({})

        assert result is True
        assert (workspace / "agents" / "pickle").exists()
        assert (workspace / "agents" / "pickle" / "AGENT.md").read_text() == "# Pickle Agent"

    def test_overwrites_existing(self, tmp_path: Path):
        """Overwrites existing assets in workspace."""
        console = Console()
        defaults = tmp_path / "defaults"
        workspace = tmp_path / "workspace"
        workspace.mkdir()
        agents_dir = workspace / "agents"
        agents_dir.mkdir()

        # Create existing asset with old content
        existing = agents_dir / "pickle"
        existing.mkdir()
        (existing / "AGENT.md").write_text("# Old Content")

        # Create default with new content
        mock_agent = defaults / "agents" / "pickle"
        mock_agent.mkdir(parents=True)
        (mock_agent / "AGENT.md").write_text("# New Content")

        step = CopyDefaultAssetsStep(workspace, console, defaults)

        with patch("questionary.checkbox") as mock_checkbox:
            mock_checkbox.return_value.ask.side_effect = [["pickle"], []]
            result = step.run({})

        assert result is True
        assert (workspace / "agents" / "pickle" / "AGENT.md").read_text() == "# New Content"


class TestConfigureMessageBusStep:
    """Tests for ConfigureMessageBusStep."""

    def test_no_platforms_disables_messagebus(self, tmp_path: Path):
        """No platform selection disables messagebus."""
        console = Console()
        defaults = tmp_path / "defaults"
        step = ConfigureMessageBusStep(tmp_path, console, defaults)

        with patch("questionary.checkbox") as mock_checkbox:
            mock_checkbox.return_value.ask.return_value = []

            state = {}
            result = step.run(state)

        assert result is True
        assert state["messagebus"]["enabled"] is False

    def test_telegram_configuration(self, tmp_path: Path):
        """Telegram selection prompts for token and users."""
        console = Console()
        defaults = tmp_path / "defaults"
        step = ConfigureMessageBusStep(tmp_path, console, defaults)

        with (
            patch("questionary.checkbox") as mock_checkbox,
            patch("questionary.text") as mock_text,
        ):
            mock_checkbox.return_value.ask.return_value = ["telegram"]
            mock_text.return_value.ask.side_effect = [
                "123:ABC",  # bot token
                "12345",  # allowed users
                "12345",  # default chat
            ]

            state = {}
            result = step.run(state)

        assert result is True
        assert state["messagebus"]["enabled"] is True
        assert state["messagebus"]["default_platform"] == "telegram"
        assert state["messagebus"]["telegram"]["bot_token"] == "123:ABC"

    def test_discord_configuration(self, tmp_path: Path):
        """Discord selection prompts for token and users."""
        console = Console()
        defaults = tmp_path / "defaults"
        step = ConfigureMessageBusStep(tmp_path, console, defaults)

        with (
            patch("questionary.checkbox") as mock_checkbox,
            patch("questionary.text") as mock_text,
        ):
            mock_checkbox.return_value.ask.return_value = ["discord"]
            mock_text.return_value.ask.side_effect = [
                "discord-token",  # bot token
                "",  # channel id (skip)
                "",  # allowed users (skip)
                "",  # default chat (skip)
            ]

            state = {}
            result = step.run(state)

        assert result is True
        assert state["messagebus"]["enabled"] is True
        assert state["messagebus"]["default_platform"] == "discord"
        assert state["messagebus"]["discord"]["bot_token"] == "discord-token"


class TestSaveConfigStep:
    """Tests for SaveConfigStep."""

    def test_writes_yaml_file(self, tmp_path: Path):
        """SaveConfigStep writes config.user.yaml."""
        console = Console()
        defaults = tmp_path / "defaults"
        workspace = tmp_path / "workspace"
        workspace.mkdir()
        step = SaveConfigStep(workspace, console, defaults)

        state = {
            "llm": {"provider": "openai", "model": "gpt-4", "api_key": "test"},
            "messagebus": {"enabled": False},
        }
        result = step.run(state)

        assert result is True
        config_path = workspace / "config.user.yaml"
        assert config_path.exists()

    def test_adds_default_agent(self, tmp_path: Path):
        """SaveConfigStep adds default_agent if not present."""
        console = Console()
        defaults = tmp_path / "defaults"
        workspace = tmp_path / "workspace"
        workspace.mkdir()
        step = SaveConfigStep(workspace, console, defaults)

        state = {
            "llm": {"provider": "openai", "model": "gpt-4", "api_key": "test"},
            "messagebus": {"enabled": False},
        }
        step.run(state)

        assert state["default_agent"] == "pickle"

    def test_validates_config(self, tmp_path: Path):
        """SaveConfigStep validates config with Pydantic."""
        console = Console()
        defaults = tmp_path / "defaults"
        workspace = tmp_path / "workspace"
        workspace.mkdir()
        step = SaveConfigStep(workspace, console, defaults)

        # Missing required fields
        state = {
            "llm": {"provider": "openai"},  # missing model and api_key
            "messagebus": {"enabled": False},
        }
        result = step.run(state)

        assert result is False
```

**Step 4: Create test_wizard.py**

```python
# tests/cli/onboarding/test_wizard.py
"""Integration tests for OnboardingWizard."""

from pathlib import Path
from unittest.mock import patch

from picklebot.cli.onboarding import OnboardingWizard


def test_wizard_instantiates():
    """OnboardingWizard can be instantiated."""
    wizard = OnboardingWizard()
    assert wizard.workspace


def test_wizard_custom_workspace():
    """OnboardingWizard accepts custom workspace path."""
    workspace = Path("/tmp/test-workspace")
    wizard = OnboardingWizard(workspace=workspace)
    assert wizard.workspace == workspace


def test_steps_list_defined():
    """OnboardingWizard has STEPS list defined."""
    from picklebot.cli.onboarding.steps import BaseStep

    assert hasattr(OnboardingWizard, "STEPS")
    assert isinstance(OnboardingWizard.STEPS, list)


def test_run_orchestrates_steps(tmp_path: Path):
    """run() executes all steps in order."""
    workspace = tmp_path / "workspace"
    wizard = OnboardingWizard(workspace=workspace)

    # Mock all steps to succeed
    with (
        patch.object(wizard, "STEPS", []),
    ):
        # Empty steps list should succeed
        result = wizard.run()
        assert result is True
```

**Step 5: Run tests to verify they fail**

```bash
uv run pytest tests/cli/onboarding/ -v
```

Expected: Import errors and test failures (steps not implemented yet)

**Step 6: Commit**

```bash
git add tests/cli/onboarding/
git commit -m "test(onboarding): add step and wizard tests"
```

---

## Task 3: Implement CheckWorkspaceStep

**Files:**
- Modify: `src/picklebot/cli/onboarding/steps.py`

**Step 1: Add CheckWorkspaceStep to steps.py**

Add after `BaseStep` class:

```python
class CheckWorkspaceStep(BaseStep):
    """Check if workspace exists and prompt for overwrite confirmation."""

    def run(self, state: dict) -> bool:
        config_path = self.workspace / "config.user.yaml"

        if config_path.exists():
            self.console.print(
                f"\n[yellow]Workspace already exists at {self.workspace}[/yellow]"
            )

            proceed = questionary.confirm(
                "This will overwrite your existing configuration. Continue?",
                default=False,
            ).ask()

            return proceed

        return True
```

**Step 2: Add questionary import at top of steps.py**

```python
import questionary
```

**Step 3: Run tests**

```bash
uv run pytest tests/cli/onboarding/test_steps.py::TestCheckWorkspaceStep -v
```

Expected: PASS

**Step 4: Commit**

```bash
git add src/picklebot/cli/onboarding/steps.py
git commit -m "feat(onboarding): implement CheckWorkspaceStep"
```

---

## Task 4: Implement SetupWorkspaceStep

**Files:**
- Modify: `src/picklebot/cli/onboarding/steps.py`

**Step 1: Add SetupWorkspaceStep**

Add after `CheckWorkspaceStep`:

```python
class SetupWorkspaceStep(BaseStep):
    """Create workspace directory and required subdirectories."""

    def run(self, state: dict) -> bool:
        self.workspace.mkdir(parents=True, exist_ok=True)

        subdirs = ["agents", "skills", "crons", "memories", ".history", ".logs"]
        for subdir in subdirs:
            (self.workspace / subdir).mkdir(exist_ok=True)

        return True
```

**Step 2: Run tests**

```bash
uv run pytest tests/cli/onboarding/test_steps.py::TestSetupWorkspaceStep -v
```

Expected: PASS

**Step 3: Commit**

```bash
git add src/picklebot/cli/onboarding/steps.py
git commit -m "feat(onboarding): implement SetupWorkspaceStep"
```

---

## Task 5: Implement ConfigureLLMStep

**Files:**
- Modify: `src/picklebot/cli/onboarding/steps.py`

**Step 1: Add ConfigureLLMStep**

Add after `SetupWorkspaceStep`:

```python
from picklebot.provider.base import LLMProvider


class ConfigureLLMStep(BaseStep):
    """Prompt user for LLM configuration."""

    def run(self, state: dict) -> bool:
        providers = LLMProvider.get_onboarding_providers()

        choices = [
            questionary.Choice(
                title=f"{p.display_name} (default: {p.default_model})",
                value=config_name,
            )
            for config_name, p in providers
        ]
        choices.append(questionary.Choice("Other (custom)", value="other"))

        provider = questionary.select("Select LLM provider:", choices=choices).ask()

        provider_cls = LLMProvider.name2provider[provider]
        model = questionary.text(
            "Model name:",
            default=provider_cls.default_model or "",
        ).ask()

        api_key = questionary.text("API key:").ask()

        api_base = questionary.text(
            "API base URL (optional):",
            default=provider_cls.api_base or "",
        ).ask()

        state["llm"] = {"provider": provider, "model": model, "api_key": api_key}
        if api_base:
            state["llm"]["api_base"] = api_base

        return True
```

**Step 2: Run tests**

```bash
uv run pytest tests/cli/onboarding/test_steps.py::TestConfigureLLMStep -v
```

Expected: PASS

**Step 3: Commit**

```bash
git add src/picklebot/cli/onboarding/steps.py
git commit -m "feat(onboarding): implement ConfigureLLMStep"
```

---

## Task 6: Implement ConfigureExtraFunctionalityStep

**Files:**
- Modify: `src/picklebot/cli/onboarding/steps.py`

**Step 1: Add ConfigureExtraFunctionalityStep**

Add after `ConfigureLLMStep`:

```python
class ConfigureExtraFunctionalityStep(BaseStep):
    """Prompt user for web tools and API configuration."""

    def run(self, state: dict) -> bool:
        selected = (
            questionary.checkbox(
                "Select extra functionality to enable:",
                choices=[
                    questionary.Choice("Web Search (Brave API)", value="websearch"),
                    questionary.Choice("Web Read (local scraping)", value="webread"),
                    questionary.Choice("API Server", value="api"),
                ],
            ).ask()
            or []
        )

        if "websearch" in selected:
            config = self._configure_websearch()
            if config:
                state["websearch"] = config

        if "webread" in selected:
            state["webread"] = {"provider": "crawl4ai"}

        if "api" in selected:
            state["api"] = {"enabled": True}

        return True

    def _configure_websearch(self) -> dict | None:
        """Prompt for web search configuration."""
        api_key = questionary.text("Brave Search API key:").ask()

        if not api_key:
            self.console.print(
                "[yellow]API key is required for web search. Skipping websearch config.[/yellow]"
            )
            return None

        return {
            "provider": "brave",
            "api_key": api_key,
        }
```

**Step 2: Run tests**

```bash
uv run pytest tests/cli/onboarding/test_steps.py::TestConfigureExtraFunctionalityStep -v
```

Expected: PASS

**Step 3: Commit**

```bash
git add src/picklebot/cli/onboarding/steps.py
git commit -m "feat(onboarding): implement ConfigureExtraFunctionalityStep"
```

---

## Task 7: Implement CopyDefaultAssetsStep

**Files:**
- Modify: `src/picklebot/cli/onboarding/steps.py`

**Step 1: Add import**

Add at top of file:

```python
import shutil
```

**Step 2: Add CopyDefaultAssetsStep**

Add after `ConfigureExtraFunctionalityStep`:

```python
class CopyDefaultAssetsStep(BaseStep):
    """Copy selected default agents and skills to workspace."""

    def run(self, state: dict) -> bool:
        default_agents = self._discover_defaults("agents")
        default_skills = self._discover_defaults("skills")

        if not default_agents and not default_skills:
            return True

        self.console.print("\n[bold]Default assets available:[/bold]")

        selected_agents = (
            questionary.checkbox(
                "Select agents to copy (will overwrite existing):",
                choices=[
                    questionary.Choice(f"agents/{name}", value=name, checked=True)
                    for name in sorted(default_agents)
                ],
            ).ask()
            or []
        )

        selected_skills = (
            questionary.checkbox(
                "Select skills to copy (will overwrite existing):",
                choices=[
                    questionary.Choice(f"skills/{name}", value=name, checked=True)
                    for name in sorted(default_skills)
                ],
            ).ask()
            or []
        )

        for name in selected_agents:
            self._copy_asset("agents", name)
        for name in selected_skills:
            self._copy_asset("skills", name)

        return True

    def _discover_defaults(self, asset_type: str) -> list[str]:
        """List available default assets of a type."""
        path = self.defaults / asset_type
        if not path.exists():
            return []
        return [d.name for d in path.iterdir() if d.is_dir()]

    def _copy_asset(self, asset_type: str, name: str) -> None:
        """Copy a single asset from defaults to workspace."""
        src = self.defaults / asset_type / name
        dst = self.workspace / asset_type / name
        if dst.exists():
            shutil.rmtree(dst)
        shutil.copytree(src, dst)
```

**Step 3: Run tests**

```bash
uv run pytest tests/cli/onboarding/test_steps.py::TestCopyDefaultAssetsStep -v
```

Expected: PASS

**Step 4: Commit**

```bash
git add src/picklebot/cli/onboarding/steps.py
git commit -m "feat(onboarding): implement CopyDefaultAssetsStep"
```

---

## Task 8: Implement ConfigureMessageBusStep

**Files:**
- Modify: `src/picklebot/cli/onboarding/steps.py`

**Step 1: Add ConfigureMessageBusStep**

Add after `CopyDefaultAssetsStep`:

```python
class ConfigureMessageBusStep(BaseStep):
    """Prompt user for MessageBus configuration."""

    def run(self, state: dict) -> bool:
        platforms = questionary.checkbox(
            "Select messaging platforms to enable:",
            choices=["telegram", "discord"],
        ).ask()

        if not platforms:
            state["messagebus"] = {"enabled": False}
            return True

        state["messagebus"] = {
            "enabled": True,
            "default_platform": platforms[0],
        }

        if "telegram" in platforms:
            state["messagebus"]["telegram"] = self._configure_telegram()

        if "discord" in platforms:
            state["messagebus"]["discord"] = self._configure_discord()

        return True

    def _configure_telegram(self) -> dict:
        """Prompt for Telegram-specific configuration."""
        bot_token = questionary.text("Telegram bot token:").ask()

        allowed_users = questionary.text(
            "Allowed user IDs (comma-separated, or press Enter for open access):",
            default="",
        ).ask()

        default_chat = questionary.text(
            "Default chat ID to proactively post to (optional, press Enter to skip):",
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

**Step 2: Run tests**

```bash
uv run pytest tests/cli/onboarding/test_steps.py::TestConfigureMessageBusStep -v
```

Expected: PASS

**Step 3: Commit**

```bash
git add src/picklebot/cli/onboarding/steps.py
git commit -m "feat(onboarding): implement ConfigureMessageBusStep"
```

---

## Task 9: Implement SaveConfigStep

**Files:**
- Modify: `src/picklebot/cli/onboarding/steps.py`

**Step 1: Add imports**

Add at top of file:

```python
import yaml
from pydantic import ValidationError
```

**Step 2: Add SaveConfigStep**

Add after `ConfigureMessageBusStep`:

```python
from picklebot.utils.config import Config


class SaveConfigStep(BaseStep):
    """Write configuration to config.user.yaml."""

    def run(self, state: dict) -> bool:
        # Set default_agent if not provided
        if "default_agent" not in state:
            state["default_agent"] = "pickle"

        # Validate config structure
        try:
            config_data = {"workspace": self.workspace}
            config_data.update(state)
            Config.model_validate(config_data)
        except ValidationError as e:
            self.console.print("\n[red]Configuration validation failed:[/red]")
            for error in e.errors():
                self.console.print(f"  - {error['loc'][0]}: {error['msg']}")
            return False

        # Write user config
        user_config_path = self.workspace / "config.user.yaml"
        with open(user_config_path, "w") as f:
            yaml.dump(state, f, default_flow_style=False)

        return True
```

**Step 3: Run tests**

```bash
uv run pytest tests/cli/onboarding/test_steps.py::TestSaveConfigStep -v
```

Expected: PASS

**Step 4: Commit**

```bash
git add src/picklebot/cli/onboarding/steps.py
git commit -m "feat(onboarding): implement SaveConfigStep"
```

---

## Task 10: Implement wizard run() method

**Files:**
- Modify: `src/picklebot/cli/onboarding/wizard.py`

**Step 1: Update wizard.py with complete implementation**

```python
# src/picklebot/cli/onboarding/wizard.py
"""Onboarding wizard orchestrator."""

from pathlib import Path

from rich.console import Console

from picklebot.cli.onboarding.steps import (
    BaseStep,
    CheckWorkspaceStep,
    ConfigureExtraFunctionalityStep,
    ConfigureLLMStep,
    ConfigureMessageBusStep,
    CopyDefaultAssetsStep,
    SaveConfigStep,
    SetupWorkspaceStep,
)


class OnboardingWizard:
    """Guides users through initial configuration."""

    DEFAULT_WORKSPACE = (
        Path(__file__).parent.parent.parent.parent / "default_workspace"
    )

    STEPS: list[type[BaseStep]] = [
        CheckWorkspaceStep,
        SetupWorkspaceStep,
        ConfigureLLMStep,
        ConfigureExtraFunctionalityStep,
        CopyDefaultAssetsStep,
        ConfigureMessageBusStep,
        SaveConfigStep,
    ]

    def __init__(self, workspace: Path | None = None):
        self.workspace = workspace or Path.home() / ".pickle-bot"

    def run(self) -> bool:
        """Run all onboarding steps. Returns True if successful."""
        console = Console()
        state: dict = {}

        console.print("\n[bold cyan]Welcome to Pickle-Bot![/bold cyan]")
        console.print("Let's set up your configuration.\n")

        for step_cls in self.STEPS:
            step = step_cls(self.workspace, console, self.DEFAULT_WORKSPACE)
            if not step.run(state):
                console.print("[yellow]Onboarding cancelled.[/yellow]")
                return False

        console.print("\n[green]Configuration saved![/green]")
        console.print(f"Config file: {self.workspace / 'config.user.yaml'}")
        console.print("Edit this file to make changes.\n")
        return True
```

**Step 2: Run wizard tests**

```bash
uv run pytest tests/cli/onboarding/test_wizard.py -v
```

Expected: PASS

**Step 3: Commit**

```bash
git add src/picklebot/cli/onboarding/wizard.py
git commit -m "feat(onboarding): implement wizard run() with step orchestration"
```

---

## Task 11: Update main.py imports

**Files:**
- Modify: `src/picklebot/cli/main.py`

**Step 1: Update import statement**

Find the import of `OnboardingWizard` and update to use new package:

```python
from picklebot.cli.onboarding import OnboardingWizard
```

**Step 2: Verify CLI still works**

```bash
uv run picklebot --help
```

Expected: Help output with no errors

**Step 3: Commit**

```bash
git add src/picklebot/cli/main.py
git commit -m "refactor(cli): update OnboardingWizard import to new package"
```

---

## Task 12: Migrate existing tests

**Files:**
- Delete: `tests/cli/test_onboarding.py`
- Verify: `tests/cli/onboarding/` covers all cases

**Step 1: Run all new onboarding tests**

```bash
uv run pytest tests/cli/onboarding/ -v
```

Expected: All PASS

**Step 2: Delete old test file**

```bash
rm tests/cli/test_onboarding.py
```

**Step 3: Run full test suite**

```bash
uv run pytest tests/cli/ -v
```

Expected: All PASS

**Step 4: Commit**

```bash
git add tests/cli/
git commit -m "refactor(tests): migrate onboarding tests to new package structure"
```

---

## Task 13: Delete old onboarding.py

**Files:**
- Delete: `src/picklebot/cli/onboarding.py`

**Step 1: Verify no references remain**

```bash
grep -r "from picklebot.cli.onboarding import" src/
grep -r "picklebot.cli.onboarding" tests/
```

Expected: Only `__init__.py` and `main.py` references

**Step 2: Delete old file**

```bash
rm src/picklebot/cli/onboarding.py
```

**Step 3: Run tests to verify nothing broke**

```bash
uv run pytest tests/cli/ -v
```

Expected: All PASS

**Step 4: Commit**

```bash
git add -A
git commit -m "refactor(onboarding): remove old monolithic onboarding.py"
```

---

## Task 14: Final verification and cleanup

**Step 1: Run full test suite**

```bash
uv run pytest -v
```

Expected: All PASS

**Step 2: Run linting**

```bash
uv run black . && uv run ruff check .
```

Expected: No errors

**Step 3: Fix any lint issues and commit**

```bash
git add -A
git commit -m "style: format and lint after onboarding refactor"
```

---

## Summary

**Files created:**
- `src/picklebot/cli/onboarding/__init__.py`
- `src/picklebot/cli/onboarding/steps.py`
- `src/picklebot/cli/onboarding/wizard.py`
- `tests/cli/onboarding/__init__.py`
- `tests/cli/onboarding/test_steps.py`
- `tests/cli/onboarding/test_wizard.py`

**Files deleted:**
- `src/picklebot/cli/onboarding.py`
- `tests/cli/test_onboarding.py`

**Files modified:**
- `src/picklebot/cli/main.py` (import update)
