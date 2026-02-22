# Onboarding Enhancement Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Enhance onboarding with auto-discovered LLM providers and bundled default agents/skills.

**Architecture:** Add abstract properties to LLMProvider for onboarding metadata (display_name, default_model, env_var, api_base). Onboarding wizard uses `name2provider` registry to auto-generate provider choices. Default agents/skills stored in `default_workspace/` and copied during onboarding with multi-select.

**Tech Stack:** Python ABCs, questionary, pathlib, shutil

---

## Task 1: Add Abstract Properties to LLMProvider

**Files:**
- Modify: `src/picklebot/provider/base.py`
- Test: `tests/provider/test_base.py` (new)

**Step 1: Write the failing tests**

Create `tests/provider/test_base.py`:

```python
"""Tests for LLMProvider base class."""

import pytest

from picklebot.provider.base import LLMProvider
from picklebot.provider.providers import (
    AnthropicProvider,
    OpenAIProvider,
    OtherProvider,
    ZaiProvider,
)


class TestProviderMetadata:
    """Test provider metadata properties."""

    def test_openai_has_required_metadata(self):
        assert OpenAIProvider.display_name == "OpenAI"
        assert OpenAIProvider.default_model == "gpt-4o"
        assert OpenAIProvider.env_var == "OPENAI_API_KEY"

    def test_anthropic_has_required_metadata(self):
        assert AnthropicProvider.display_name == "Anthropic Claude"
        assert AnthropicProvider.default_model == "claude-3-5-sonnet-latest"
        assert AnthropicProvider.env_var == "ANTHROPIC_API_KEY"

    def test_zai_has_required_metadata(self):
        assert ZaiProvider.display_name == "Z.ai"
        assert ZaiProvider.default_model == "zai-1.0"
        assert ZaiProvider.env_var == "ZAI_API_KEY"

    def test_other_has_required_metadata(self):
        assert OtherProvider.display_name == "Other (custom)"
        assert OtherProvider.default_model == ""

    def test_env_var_is_optional(self):
        # OtherProvider has no env_var
        assert OtherProvider.env_var is None

    def test_api_base_is_optional(self):
        # None of our providers define api_base by default
        assert OpenAIProvider.api_base is None


class TestGetOnboardingProviders:
    """Test get_onboarding_providers classmethod."""

    def test_returns_list_of_tuples(self):
        providers = LLMProvider.get_onboarding_providers()
        assert isinstance(providers, list)
        assert all(isinstance(p, tuple) and len(p) == 2 for p in providers)

    def test_excludes_other_provider(self):
        providers = LLMProvider.get_onboarding_providers()
        config_names = [name for name, _ in providers]
        assert "other" not in config_names

    def test_includes_main_providers(self):
        providers = LLMProvider.get_onboarding_providers()
        config_names = [name for name, _ in providers]
        assert "openai" in config_names
        assert "anthropic" in config_names
        assert "zai" in config_names

    def test_returns_provider_classes(self):
        providers = LLMProvider.get_onboarding_providers()
        for config_name, provider_cls in providers:
            assert issubclass(provider_cls, LLMProvider)
            assert provider_cls.display_name  # has metadata
```

**Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/provider/test_base.py -v`
Expected: FAIL - display_name, default_model not defined, get_onboarding_providers not defined

**Step 3: Add abstract properties to LLMProvider**

Modify `src/picklebot/provider/base.py`:

```python
"""Base LLM provider abstraction."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Optional, cast

from litellm import acompletion, Choices
from litellm.types.completion import ChatCompletionMessageParam as Message

from picklebot.utils.config import LLMConfig


@dataclass
class LLMToolCall:
    """
    A tool/function call from the LLM.

    Simplified adapter over litellm's ChatCompletionMessageToolCall
    which has nested structure (function.name, function.arguments).
    """

    id: str
    name: str
    arguments: str  # JSON string


class LLMProvider(ABC):
    """
    Abstract base class for LLM providers.

    All providers inherit from this and get the default `chat` implementation
    via litellm. Subclasses only need to define `provider_config_name`.
    """

    provider_config_name: list[str]
    name2provider: dict[str, type["LLMProvider"]] = {}

    @property
    @abstractmethod
    def display_name(self) -> str:
        """Friendly name for onboarding wizard."""
        ...

    @property
    @abstractmethod
    def default_model(self) -> str:
        """Default model for this provider."""
        ...

    @property
    def env_var(self) -> str | None:
        """Environment variable for API key (optional)."""
        return None

    @property
    def api_base(self) -> str | None:
        """Default API base URL (optional)."""
        return None

    def __init__(
        self,
        model: str,
        api_key: str,
        api_base: Optional[str] = None,
        **kwargs: Any,
    ):
        self.model = model
        self.api_key = api_key
        self.api_base = api_base
        self._settings = kwargs

    def __init_subclass__(cls):
        for c_name in cls.provider_config_name:
            LLMProvider.name2provider[c_name] = cls
        return super().__init_subclass__()

    @classmethod
    def get_onboarding_providers(cls) -> list[tuple[str, type["LLMProvider"]]]:
        """Return list of (config_name, provider_class) for onboarding wizard.

        Returns unique providers (first config_name only), excluding "other".
        "other" is handled separately as fallback.
        """
        seen = set()
        providers = []
        for config_name, provider_cls in cls.name2provider.items():
            if config_name == "other":
                continue
            if provider_cls not in seen:
                seen.add(provider_cls)
                providers.append((config_name, provider_cls))
        return providers

    @staticmethod
    def from_config(config: LLMConfig) -> "LLMProvider":
        """Create a provider from config."""
        provider_name = config.provider.lower()
        if provider_name not in LLMProvider.name2provider:
            raise ValueError(f"Unknown provider: {provider_name}")

        provider_class = LLMProvider.name2provider[provider_name]
        return provider_class(
            model=config.model,
            api_key=config.api_key,
            api_base=config.api_base,
        )

    async def chat(
        self,
        messages: list[Message],
        tools: Optional[list[dict[str, Any]]] = None,
        **kwargs: Any,
    ) -> tuple[str, list[LLMToolCall]]:
        """
        Send a chat request to the LLM.

        Default implementation using litellm. Subclasses can override
        if provider-specific behavior is needed.
        """
        request_kwargs: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "api_key": self.api_key,
        }

        if self.api_base:
            request_kwargs["api_base"] = self.api_base
        if tools:
            request_kwargs["tools"] = tools
        request_kwargs.update(kwargs)

        response = await acompletion(**request_kwargs)

        message = cast(Choices, response.choices[0]).message

        return (
            message.content or "",
            [
                LLMToolCall(
                    id=tc["id"],
                    name=tc["function"]["name"],
                    arguments=tc["function"]["arguments"],
                )
                for tc in (message.tool_calls or [])
            ],
        )
```

**Step 4: Add metadata to provider subclasses**

Modify `src/picklebot/provider/providers.py`:

```python
"""Concrete LLM provider implementations."""

from picklebot.provider.base import LLMProvider


class ZaiProvider(LLMProvider):
    """Z.ai LLM provider (OpenAI-compatible API)."""

    provider_config_name = ["zai", "z_ai"]
    display_name = "Z.ai"
    default_model = "zai-1.0"
    env_var = "ZAI_API_KEY"


class OpenAIProvider(LLMProvider):
    """OpenAI LLM provider."""

    provider_config_name = ["openai"]
    display_name = "OpenAI"
    default_model = "gpt-4o"
    env_var = "OPENAI_API_KEY"


class AnthropicProvider(LLMProvider):
    """Anthropic Claude LLM provider."""

    provider_config_name = ["anthropic", "claude"]
    display_name = "Anthropic Claude"
    default_model = "claude-3-5-sonnet-latest"
    env_var = "ANTHROPIC_API_KEY"


class OtherProvider(LLMProvider):
    """Fallback for custom/self-hosted providers."""

    provider_config_name = ["other"]
    display_name = "Other (custom)"
    default_model = ""
```

**Step 5: Run tests to verify they pass**

Run: `uv run pytest tests/provider/test_base.py -v`
Expected: PASS

**Step 6: Commit**

```bash
git add src/picklebot/provider/base.py src/picklebot/provider/providers.py tests/provider/test_base.py
git commit -m "feat(provider): add onboarding metadata to LLMProvider"
```

---

## Task 2: Update Onboarding Wizard - LLM Configuration

**Files:**
- Modify: `src/picklebot/cli/onboarding.py:34-63`
- Modify: `tests/cli/test_onboarding.py:34-50`

**Step 1: Update the test for auto-discovered providers**

Modify `tests/cli/test_onboarding.py`, update `test_configure_llm_stores_state`:

```python
def test_configure_llm_stores_state():
    """Test that configure_llm stores LLM config in state."""
    wizard = OnboardingWizard()

    with (
        patch("questionary.select") as mock_select,
        patch("questionary.text") as mock_text,
    ):
        # Mock select returns the provider config_name
        mock_select.return_value.ask.return_value = "openai"
        # Model uses provider default, so user just presses enter
        # Then api_key, then empty api_base
        mock_text.return_value.ask.side_effect = ["", "sk-test-key", ""]

        wizard.configure_llm()

    assert wizard.state["llm"]["provider"] == "openai"
    assert wizard.state["llm"]["model"] == "gpt-4o"  # default from provider
    assert wizard.state["llm"]["api_key"] == "sk-test-key"
    assert wizard.state["llm"].get("api_base") is None


def test_configure_llm_other_provider_prompts_api_base():
    """Test that other provider prompts for api_base."""
    wizard = OnboardingWizard()

    with (
        patch("questionary.select") as mock_select,
        patch("questionary.text") as mock_text,
    ):
        mock_select.return_value.ask.return_value = "other"
        mock_text.return_value.ask.side_effect = [
            "llama-3",  # model (no default)
            "my-key",  # api_key
            "http://localhost:11434",  # api_base
        ]

        wizard.configure_llm()

    assert wizard.state["llm"]["provider"] == "other"
    assert wizard.state["llm"]["model"] == "llama-3"
    assert wizard.state["llm"]["api_base"] == "http://localhost:11434"
```

**Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/cli/test_onboarding.py::test_configure_llm_stores_state -v`
Expected: FAIL - still uses old hardcoded logic

**Step 3: Update configure_llm to use auto-discovery**

Modify `src/picklebot/cli/onboarding.py`, update the `configure_llm` method:

```python
from picklebot.provider.base import LLMProvider

# ... in OnboardingWizard class ...

    def configure_llm(self) -> None:
        """Prompt user for LLM configuration using auto-discovered providers."""
        # Get providers for onboarding
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

        # Get provider class for defaults
        provider_cls = LLMProvider.name2provider[provider]

        # Model with provider default
        model = questionary.text(
            "Model name:",
            default=provider_cls.default_model,
        ).ask()

        # API key with env var hint
        env_hint = f" (or set {provider_cls.env_var})" if provider_cls.env_var else ""
        api_key = questionary.text(f"API key{env_hint}:").ask()

        # API base (only for "other" or if provider has default)
        api_base = ""
        if provider == "other" or provider_cls.api_base:
            api_base = questionary.text(
                "API base URL (optional):",
                default=provider_cls.api_base or "",
            ).ask()

        self.state["llm"] = {"provider": provider, "model": model, "api_key": api_key}
        if api_base:
            self.state["llm"]["api_base"] = api_base
```

**Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/cli/test_onboarding.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/picklebot/cli/onboarding.py tests/cli/test_onboarding.py
git commit -m "feat(onboarding): use auto-discovered providers in configure_llm"
```

---

## Task 3: Add Default Asset Copying to Onboarding

**Files:**
- Modify: `src/picklebot/cli/onboarding.py`
- Modify: `tests/cli/test_onboarding.py`

**Step 1: Write the failing tests**

Add to `tests/cli/test_onboarding.py`:

```python
def test_discover_defaults_returns_empty_if_no_defaults():
    """Test _discover_defaults returns empty list if default_workspace missing."""
    wizard = OnboardingWizard()
    # Point to non-existent default workspace
    wizard.DEFAULT_WORKSPACE = Path("/nonexistent")

    result = wizard._discover_defaults("agents")
    assert result == []


def test_discover_defaults_returns_asset_names():
    """Test _discover_defaults returns names of assets in default_workspace."""
    wizard = OnboardingWizard()
    # Will use actual default_workspace if it exists
    result = wizard._discover_defaults("agents")
    # Just verify it returns a list
    assert isinstance(result, list)


def test_copy_asset_copies_directory():
    """Test _copy_asset copies asset from defaults to workspace."""
    with tempfile.TemporaryDirectory() as tmpdir:
        workspace = Path(tmpdir) / "workspace"
        workspace.mkdir()
        (workspace / "agents").mkdir()

        wizard = OnboardingWizard(workspace=workspace)

        # Create a mock default asset
        mock_defaults = Path(tmpdir) / "defaults"
        mock_defaults.mkdir()
        mock_agent = mock_defaults / "agents" / "test-agent"
        mock_agent.mkdir(parents=True)
        (mock_agent / "AGENT.md").write_text("# Test Agent")

        wizard.DEFAULT_WORKSPACE = mock_defaults
        wizard._copy_asset("agents", "test-agent")

        # Verify copied
        copied = workspace / "agents" / "test-agent"
        assert copied.exists()
        assert (copied / "AGENT.md").read_text() == "# Test Agent"


def test_copy_asset_overwrites_existing():
    """Test _copy_asset overwrites existing asset."""
    with tempfile.TemporaryDirectory() as tmpdir:
        workspace = Path(tmpdir) / "workspace"
        workspace.mkdir()
        agents_dir = workspace / "agents"
        agents_dir.mkdir()

        # Create existing asset with old content
        existing = agents_dir / "test-agent"
        existing.mkdir()
        (existing / "AGENT.md").write_text("# Old Content")

        wizard = OnboardingWizard(workspace=workspace)

        # Create mock default with new content
        mock_defaults = Path(tmpdir) / "defaults"
        mock_defaults.mkdir()
        mock_agent = mock_defaults / "agents" / "test-agent"
        mock_agent.mkdir(parents=True)
        (mock_agent / "AGENT.md").write_text("# New Content")

        wizard.DEFAULT_WORKSPACE = mock_defaults
        wizard._copy_asset("agents", "test-agent")

        # Verify overwritten
        copied = workspace / "agents" / "test-agent"
        assert (copied / "AGENT.md").read_text() == "# New Content"


def test_copy_default_assets_prompts_user():
    """Test copy_default_assets shows multi-select and copies selected."""
    with tempfile.TemporaryDirectory() as tmpdir:
        workspace = Path(tmpdir) / "workspace"
        workspace.mkdir()
        (workspace / "agents").mkdir()
        (workspace / "skills").mkdir()

        wizard = OnboardingWizard(workspace=workspace)

        # Create mock defaults
        mock_defaults = Path(tmpdir) / "defaults"
        mock_defaults.mkdir()
        mock_agent = mock_defaults / "agents" / "pickle"
        mock_agent.mkdir(parents=True)
        (mock_agent / "AGENT.md").write_text("# Pickle")

        wizard.DEFAULT_WORKSPACE = mock_defaults

        with patch("questionary.checkbox") as mock_checkbox:
            # User selects pickle agent, no skills
            mock_checkbox.return_value.ask.side_effect = [["pickle"], []]

            wizard.copy_default_assets()

        # Verify copied
        assert (workspace / "agents" / "pickle").exists()


def test_copy_default_assets_skips_if_no_defaults():
    """Test copy_default_assets does nothing if no default workspace."""
    wizard = OnboardingWizard()
    wizard.DEFAULT_WORKSPACE = Path("/nonexistent")

    with patch("questionary.checkbox") as mock_checkbox:
        wizard.copy_default_assets()

    # Should not prompt user
    mock_checkbox.assert_not_called()
```

**Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/cli/test_onboarding.py -v -k "default"`
Expected: FAIL - methods not implemented

**Step 3: Add copy_default_assets methods**

Modify `src/picklebot/cli/onboarding.py`, add imports and methods:

```python
import shutil
from pathlib import Path

# ... existing imports ...


class OnboardingWizard:
    """Guides users through initial configuration."""

    DEFAULT_WORKSPACE = Path(__file__).parent.parent.parent / "default_workspace"

    # ... existing __init__ ...

    # ... existing methods ...

    def copy_default_assets(self) -> None:
        """Copy selected default agents and skills to workspace."""
        default_agents = self._discover_defaults("agents")
        default_skills = self._discover_defaults("skills")

        if not default_agents and not default_skills:
            return

        console = Console()
        console.print("\n[bold]Default assets available:[/bold]")

        # Multi-select for agents
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

        # Multi-select for skills
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

        # Copy selected
        for name in selected_agents:
            self._copy_asset("agents", name)
        for name in selected_skills:
            self._copy_asset("skills", name)

    def _discover_defaults(self, asset_type: str) -> list[str]:
        """List available default assets of a type."""
        path = self.DEFAULT_WORKSPACE / asset_type
        if not path.exists():
            return []
        return [d.name for d in path.iterdir() if d.is_dir()]

    def _copy_asset(self, asset_type: str, name: str) -> None:
        """Copy a single asset from defaults to workspace."""
        src = self.DEFAULT_WORKSPACE / asset_type / name
        dst = self.workspace / asset_type / name
        if dst.exists():
            shutil.rmtree(dst)
        shutil.copytree(src, dst)
```

**Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/cli/test_onboarding.py -v -k "default"`
Expected: PASS

**Step 5: Commit**

```bash
git add src/picklebot/cli/onboarding.py tests/cli/test_onboarding.py
git commit -m "feat(onboarding): add copy_default_assets for bundled agents/skills"
```

---

## Task 4: Add Workspace Overwrite Warning and Update Run Flow

**Files:**
- Modify: `src/picklebot/cli/onboarding.py`
- Modify: `tests/cli/test_onboarding.py`

**Step 1: Write the failing tests**

Add to `tests/cli/test_onboarding.py`:

```python
def test_check_existing_workspace_returns_true_if_no_config():
    """Test check_existing_workspace returns True when config doesn't exist."""
    with tempfile.TemporaryDirectory() as tmpdir:
        workspace = Path(tmpdir) / "workspace"
        wizard = OnboardingWizard(workspace=workspace)

        result = wizard.check_existing_workspace()

        assert result is True


def test_check_existing_workspace_prompts_if_config_exists():
    """Test check_existing_workspace prompts user when config exists."""
    with tempfile.TemporaryDirectory() as tmpdir:
        workspace = Path(tmpdir) / "workspace"
        workspace.mkdir()
        (workspace / "config.user.yaml").write_text("llm: {}")

        wizard = OnboardingWizard(workspace=workspace)

        with patch("questionary.confirm") as mock_confirm:
            mock_confirm.return_value.ask.return_value = True
            result = wizard.check_existing_workspace()

        mock_confirm.assert_called_once()
        assert result is True


def test_check_existing_workspace_returns_false_if_user_declines():
    """Test check_existing_workspace returns False if user says no."""
    with tempfile.TemporaryDirectory() as tmpdir:
        workspace = Path(tmpdir) / "workspace"
        workspace.mkdir()
        (workspace / "config.user.yaml").write_text("llm: {}")

        wizard = OnboardingWizard(workspace=workspace)

        with patch("questionary.confirm") as mock_confirm:
            mock_confirm.return_value.ask.return_value = False
            result = wizard.check_existing_workspace()

        assert result is False


def test_run_includes_copy_default_assets():
    """Test that run() calls copy_default_assets."""
    with tempfile.TemporaryDirectory() as tmpdir:
        workspace = Path(tmpdir) / "workspace"
        wizard = OnboardingWizard(workspace=workspace)

        with (
            patch.object(wizard, "check_existing_workspace", return_value=True),
            patch.object(wizard, "setup_workspace"),
            patch.object(wizard, "configure_llm"),
            patch.object(wizard, "copy_default_assets") as mock_copy,
            patch.object(wizard, "configure_messagebus"),
            patch.object(wizard, "save_config", return_value=True),
        ):
            wizard.run()

        mock_copy.assert_called_once()


def test_run_returns_false_if_user_cancels_overwrite():
    """Test run returns False if user cancels at overwrite prompt."""
    with tempfile.TemporaryDirectory() as tmpdir:
        workspace = Path(tmpdir) / "workspace"
        workspace.mkdir()
        (workspace / "config.user.yaml").write_text("llm: {}")

        wizard = OnboardingWizard(workspace=workspace)

        with patch("questionary.confirm") as mock_confirm:
            mock_confirm.return_value.ask.return_value = False
            result = wizard.run()

        assert result is False
```

Also update the existing `test_run_orchestrates_all_steps`:

```python
def test_run_orchestrates_all_steps():
    """Test that run() calls all steps in order."""
    with tempfile.TemporaryDirectory() as tmpdir:
        workspace = Path(tmpdir) / "test-workspace"
        wizard = OnboardingWizard(workspace=workspace)

        with (
            patch.object(wizard, "check_existing_workspace", return_value=True),
            patch.object(wizard, "setup_workspace") as mock_setup,
            patch.object(wizard, "configure_llm") as mock_llm,
            patch.object(wizard, "copy_default_assets") as mock_copy,
            patch.object(wizard, "configure_messagebus") as mock_bus,
            patch.object(wizard, "save_config") as mock_save,
        ):
            wizard.run()

        mock_setup.assert_called_once()
        mock_llm.assert_called_once()
        mock_copy.assert_called_once()
        mock_bus.assert_called_once()
        mock_save.assert_called_once()
```

**Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/cli/test_onboarding.py -v -k "existing or run"`
Expected: FAIL - check_existing_workspace not defined, run doesn't call copy_default_assets

**Step 3: Add check_existing_workspace method and update run**

Modify `src/picklebot/cli/onboarding.py`:

```python
    def check_existing_workspace(self) -> bool:
        """Check if workspace exists and prompt for overwrite confirmation."""
        config_path = self.workspace / "config.user.yaml"

        if config_path.exists():
            console = Console()
            console.print(
                f"\n[yellow]Workspace already exists at {self.workspace}[/yellow]"
            )

            proceed = questionary.confirm(
                "This will overwrite your existing configuration. Continue?",
                default=False,
            ).ask()

            return proceed

        return True

    def run(self) -> bool:
        """Run the complete onboarding flow. Returns True if successful."""
        console = Console()

        # Check for existing workspace
        if not self.check_existing_workspace():
            console.print("[yellow]Onboarding cancelled.[/yellow]")
            return False

        console.print("\n[bold cyan]Welcome to Pickle-Bot![/bold cyan]")
        console.print("Let's set up your configuration.\n")

        self.setup_workspace()
        self.configure_llm()
        self.copy_default_assets()
        self.configure_messagebus()

        if self.save_config():
            console.print("\n[green]Configuration saved![/green]")
            console.print(f"Config file: {self.workspace / 'config.user.yaml'}")
            console.print("Edit this file to make changes.\n")
            return True

        return False
```

**Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/cli/test_onboarding.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/picklebot/cli/onboarding.py tests/cli/test_onboarding.py
git commit -m "feat(onboarding): add overwrite warning and copy_default_assets to run flow"
```

---

## Task 5: Create Default Workspace Assets

**Files:**
- Create: `default_workspace/agents/pickle/AGENT.md`
- Create: `default_workspace/agents/cookie/AGENT.md`
- Create: `default_workspace/skills/skill-creator/SKILL.md`
- Create: `default_workspace/skills/cron-ops/SKILL.md`

**Step 1: Create pickle agent**

Create `default_workspace/agents/pickle/AGENT.md`:

```markdown
---
name: Pickle
description: A friendly general-purpose assistant
temperature: 0.7
---

You are Pickle, a friendly and helpful AI assistant. You help users with a wide variety of tasks including answering questions, brainstorming ideas, writing content, and solving problems.

Be conversational and approachable. When you don't know something, admit it honestly. When you make a mistake, correct yourself gracefully.

You have access to various tools and skills. Use them when appropriate to help the user accomplish their goals.
```

**Step 2: Create cookie agent**

Create `default_workspace/agents/cookie/AGENT.md`:

```markdown
---
name: Cookie
description: A focused task-oriented assistant
temperature: 0.3
---

You are Cookie, a focused and efficient AI assistant. You excel at completing specific tasks with precision and clarity.

Be concise and direct. Focus on getting things done rather than extended conversation. When working on code or technical tasks, be thorough and accurate.

You have access to various tools and skills. Use them strategically to accomplish the user's objectives efficiently.
```

**Step 3: Create skill-creator skill**

Create `default_workspace/skills/skill-creator/SKILL.md`:

```markdown
---
name: Skill Creator
description: Help users create new skills for pickle-bot
tools:
  - write_file
  - read_file
---

# Skill Creator

You help users create new skills for pickle-bot.

## What is a Skill?

A skill is a reusable prompt that enhances an agent's capabilities. Skills are stored as `SKILL.md` files with YAML frontmatter.

## Creating a Skill

When a user wants to create a skill:

1. Ask what the skill should do
2. Suggest a name and description
3. Draft the skill content
4. Use `write_file` to create the skill at `skills/<name>/SKILL.md`

## Skill Template

```markdown
---
name: Skill Name
description: What this skill does
tools:
  - tool_name
---

Skill instructions go here.
```
```

**Step 4: Create cron-ops skill**

Create `default_workspace/skills/cron-ops/SKILL.md`:

```markdown
---
name: Cron Ops
description: Manage scheduled cron jobs
tools:
  - read_file
  - write_file
  - list_files
---

# Cron Operations

You help users manage scheduled cron jobs in pickle-bot.

## What is a Cron?

A cron is a scheduled task that runs at specified intervals. Crons are stored as `CRON.md` files with YAML frontmatter defining the schedule.

## Cron Schedule Format

Uses standard cron syntax: `minute hour day month weekday`

Examples:
- `0 9 * * *` - Every day at 9:00 AM
- `*/30 * * * *` - Every 30 minutes
- `0 0 * * 0` - Every Sunday at midnight

## Creating a Cron

When a user wants to create a cron:

1. Ask what task should run and when
2. Determine the schedule
3. Draft the cron definition
4. Use `write_file` to create at `crons/<name>/CRON.md`
```

**Step 5: Verify files created**

Run: `ls -la default_workspace/agents/ default_workspace/skills/`
Expected: Both directories with their subdirectories

**Step 6: Commit**

```bash
git add default_workspace/
git commit -m "feat: add default agents (pickle, cookie) and skills (skill-creator, cron-ops)"
```

---

## Task 6: Final Verification

**Step 1: Run all tests**

Run: `uv run pytest tests/ -v`
Expected: All tests pass

**Step 2: Run lint and format**

Run: `uv run black . && uv run ruff check .`
Expected: No errors

**Step 3: Manual test of onboarding**

Run: `uv run picklebot init` (in a temp directory or with test workspace)
Verify:
- Provider list shows auto-discovered providers with defaults
- Overwrite warning appears if config exists
- Default assets multi-select works
- Assets copied correctly

**Step 4: Final commit (if any fixes needed)**

```bash
git add -A
git commit -m "fix: any issues found during verification"
```
