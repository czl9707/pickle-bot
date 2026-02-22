# Onboarding Enhancement Design

## Overview

Enhance the onboarding flow with:
1. Auto-discovered LLM providers (eliminate hardcoded if/else logic)
2. Bundled default agents and skills that ship with the package

## Goals

- Make adding new LLM providers easier (just define a class, onboarding auto-picks it up)
- Provide better UX with provider-specific defaults and hints (env var names, default models)
- Give users a quick start with pre-bundled agents and skills
- Allow users to opt-out of default assets they don't want

## Design

### 1. LLMProvider Metadata

Add abstract properties to `LLMProvider` base class:

```python
class LLMProvider(ABC):
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
```

Provider subclasses use class attributes to satisfy abstract properties:

```python
class OpenAIProvider(LLMProvider):
    provider_config_name = ["openai"]
    display_name = "OpenAI"
    default_model = "gpt-4o"
    env_var = "OPENAI_API_KEY"

class AnthropicProvider(LLMProvider):
    provider_config_name = ["anthropic", "claude"]
    display_name = "Anthropic Claude"
    default_model = "claude-3-5-sonnet-latest"
    env_var = "ANTHROPIC_API_KEY"

class ZaiProvider(LLMProvider):
    provider_config_name = ["zai", "z_ai"]
    display_name = "Z.ai"
    default_model = "zai-1.0"
    env_var = "ZAI_API_KEY"

class OtherProvider(LLMProvider):
    provider_config_name = ["other"]
    display_name = "Other (custom)"
    default_model = ""  # User must enter
```

Add helper method for onboarding:

```python
@classmethod
def get_onboarding_providers(cls) -> list[tuple[str, type["LLMProvider"]]]:
    """Return list of (config_name, provider_class) for onboarding wizard.

    Returns unique providers (first config_name only), excluding "other".
    "other" is handled separately as fallback.
    """
```

### 2. Onboarding Wizard LLM Configuration

Auto-discover providers from `name2provider`:

```python
def configure_llm(self) -> None:
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

    model = questionary.text("Model name:", default=provider_cls.default_model).ask()

    env_hint = f" (or set {provider_cls.env_var})" if provider_cls.env_var else ""
    api_key = questionary.text(f"API key{env_hint}:").ask()

    api_base = ""
    if provider == "other" or provider_cls.api_base:
        api_base = questionary.text(
            "API base URL (optional):",
            default=provider_cls.api_base or "",
        ).ask()
```

### 3. Default Assets

**Directory structure (`default_workspace/` at project root):**

```
default_workspace/
├── agents/
│   ├── pickle/
│   │   └── AGENT.md
│   └── cookie/
│       └── AGENT.md
└── skills/
    ├── skill-creator/
    │   └── SKILL.md
    └── cron-ops/
        └── SKILL.md
```

**Asset copy method:**

```python
class OnboardingWizard:
    DEFAULT_WORKSPACE = Path(__file__).parent.parent.parent / "default_workspace"

    def copy_default_assets(self) -> None:
        """Copy selected default agents and skills to workspace."""
        default_agents = self._discover_defaults("agents")
        default_skills = self._discover_defaults("skills")

        if not default_agents and not default_skills:
            return

        # Multi-select with overwrite warning
        selected_agents = questionary.checkbox(
            "Select agents to copy (will overwrite existing):",
            choices=[
                questionary.Choice(f"agents/{name}", value=name, checked=True)
                for name in default_agents
            ],
        ).ask() or []

        selected_skills = questionary.checkbox(
            "Select skills to copy (will overwrite existing):",
            choices=[
                questionary.Choice(f"skills/{name}", value=name, checked=True)
                for name in default_skills
            ],
        ).ask() or []

        for name in selected_agents:
            self._copy_asset("agents", name)
        for name in selected_skills:
            self._copy_asset("skills", name)

    def _discover_defaults(self, asset_type: str) -> list[str]:
        path = self.DEFAULT_WORKSPACE / asset_type
        if not path.exists():
            return []
        return [d.name for d in path.iterdir() if d.is_dir()]

    def _copy_asset(self, asset_type: str, name: str) -> None:
        src = self.DEFAULT_WORKSPACE / asset_type / name
        dst = self.workspace / asset_type / name
        if dst.exists():
            shutil.rmtree(dst)
        shutil.copytree(src, dst)
```

### 4. Init Flow & Overwrite Warning

**Flow order:**

1. `check_existing_workspace()` - Warn if config exists, prompt to continue
2. `setup_workspace()` - Create directories
3. `configure_llm()` - Auto-discovered providers
4. `copy_default_assets()` - Multi-select with overwrite warning
5. `configure_messagebus()` - Platform setup
6. `save_config()` - Persist configuration

**Workspace overwrite check:**

```python
def check_existing_workspace(self) -> bool:
    config_path = self.workspace / "config.user.yaml"

    if config_path.exists():
        proceed = questionary.confirm(
            "This will overwrite your existing configuration. Continue?",
            default=False,
        ).ask()
        return proceed

    return True

def run(self) -> bool:
    if not self.check_existing_workspace():
        return False

    self.setup_workspace()
    self.configure_llm()
    self.copy_default_assets()
    self.configure_messagebus()

    return self.save_config()
```

## Files to Modify

1. `src/picklebot/provider/base.py` - Add abstract properties and helper method
2. `src/picklebot/provider/providers.py` - Add metadata to existing providers, add OtherProvider
3. `src/picklebot/cli/onboarding.py` - Update configure_llm, add copy_default_assets, update run

## Files to Create

1. `default_workspace/agents/pickle/AGENT.md`
2. `default_workspace/agents/cookie/AGENT.md`
3. `default_workspace/skills/skill-creator/SKILL.md`
4. `default_workspace/skills/cron-ops/SKILL.md`

## Testing

- Test onboarding with each provider type
- Test overwrite warning appears when config exists
- Test default asset multi-select and copy
- Test skipping default assets (unselect all)
- Test adding new provider auto-appears in onboarding
