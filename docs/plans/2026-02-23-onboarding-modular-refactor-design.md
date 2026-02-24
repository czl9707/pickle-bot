# Onboarding Modular Refactor Design

Refactor the onboarding wizard into modular step classes for improved testability, extensibility, and readability.

## Goals

- **Testability**: Each step independently testable without mocking the whole wizard
- **Extensibility**: Easy to add/remove/reorder steps without touching core wizard code
- **Readability**: Smaller, focused modules that are easier to understand

## Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Pattern | Step classes | Clean separation, easy to test, explicit interface |
| State management | Mutable dict passed explicitly | Simple, flexible, keeps state flow visible |
| Step interface | `run(state: dict) -> bool` | Returns success/failure, handles cancellation gracefully |
| Error handling | Abort immediately on failure | Keeps flow simple, matches current behavior |
| File structure | Single `steps.py` file | All steps in one place, easy to find |
| Helpers | Keep as methods on step classes | Self-contained, no extra abstraction |

## File Structure

```
src/picklebot/cli/
├── onboarding/
│   ├── __init__.py          # exports OnboardingWizard
│   ├── wizard.py            # orchestrator with STEPS list
│   └── steps.py             # BaseStep + all step classes
└── main.py                  # imports from onboarding package
```

Public API unchanged: `from picklebot.cli.onboarding import OnboardingWizard`

## Step Interface

```python
class BaseStep:
    """Base class for onboarding steps."""

    def __init__(self, workspace: Path, console: Console, defaults: Path):
        self.workspace = workspace
        self.console = console
        self.defaults = defaults  # path to default_workspace

    def run(self, state: dict) -> bool:
        """Execute step. Return True on success, False to abort."""
        raise NotImplementedError
```

## Step Classes

| Class | Responsibility | State keys written |
|-------|---------------|-------------------|
| `CheckWorkspaceStep` | Prompt to overwrite if config exists | (none) |
| `SetupWorkspaceStep` | Create directories | (none) |
| `ConfigureLLMStep` | Provider, model, API key | `llm` |
| `ConfigureExtraFunctionalityStep` | Websearch, webread, API server | `websearch`, `webread`, `api` |
| `CopyDefaultAssetsStep` | Copy agents/skills from defaults | (none) |
| `ConfigureMessageBusStep` | Telegram/Discord setup | `messagebus` |
| `SaveConfigStep` | Validate & write YAML, add `default_agent` | `default_agent` |

### ConfigureExtraFunctionalityStep

Prompts user to enable optional features:

- **Web Search** (Brave API) - prompts for API key
- **Web Read** (crawl4ai) - no additional config needed
- **API Server** - just a bool toggle, uses default host/port (127.0.0.1:8000)

```python
class ConfigureExtraFunctionalityStep(BaseStep):
    def run(self, state: dict) -> bool:
        selected = questionary.checkbox(
            "Select extra functionality to enable:",
            choices=[
                questionary.Choice("Web Search (Brave API)", value="websearch"),
                questionary.Choice("Web Read (local scraping)", value="webread"),
                questionary.Choice("API Server", value="api"),
            ],
        ).ask() or []

        if "websearch" in selected:
            api_key = questionary.text("Brave Search API key:").ask()
            if api_key:
                state["websearch"] = {"provider": "brave", "api_key": api_key}
            else:
                self.console.print("[yellow]API key required. Skipping websearch.[/yellow]")

        if "webread" in selected:
            state["webread"] = {"provider": "crawl4ai"}

        if "api" in selected:
            state["api"] = {"enabled": True}

        return True
```

## Wizard

Thin orchestrator that iterates through steps:

```python
class OnboardingWizard:
    """Guides users through initial configuration."""

    DEFAULT_WORKSPACE = Path(__file__).parent.parent.parent.parent / "default_workspace"

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

        console.print(f"Config file: {self.workspace / 'config.user.yaml'}")
        console.print("Edit this file to make changes.\n")
        return True
```

**Key changes from current:**
- No `self.state` - state is local to `run()`, passed explicitly
- `STEPS` class attribute - easy to see all steps at a glance, easy to modify
- Wizard is thin orchestrator - all logic in step classes

## Testing

```
tests/cli/onboarding/
├── test_wizard.py          # Integration: full wizard flow
├── test_steps.py           # Unit tests for all steps
```

Each step can be tested in isolation:

```python
def test_configure_llm_step_stores_state(tmp_path: Path):
    """Test ConfigureLLMStep stores config in state."""
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
```

**Benefits:**
- No need to mock the entire wizard
- Test each step with just its dependencies (workspace, console, defaults)
- Integration tests verify step ordering and wizard orchestration
- Easier to add new tests when adding new steps

## Migration

1. Create `onboarding/` package with `__init__.py`, `wizard.py`, `steps.py`
2. Extract step logic from current `OnboardingWizard` methods into step classes
3. Update `wizard.py` to use step classes
4. Update imports in `main.py`
5. Migrate tests to new structure
6. Delete old `onboarding.py`
