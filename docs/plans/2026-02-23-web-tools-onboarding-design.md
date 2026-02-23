# Web Tools Onboarding Design

**Date**: 2026-02-23
**Status**: Approved
**Author**: Design session

## Overview

Add web search and web read configuration to the onboarding wizard, allowing users to enable these tools during initial setup.

## Goals

- Let users optionally configure web tools during onboarding
- Follow existing onboarding patterns (checkbox selection like messagebus)
- Keep flow simple and non-blocking

## Non-Goals

- Validation of API keys during onboarding
- Multiple provider options in v1
- Auto-detection of existing environment variables

## Design

### Flow Position

Insert web tools configuration after LLM config, before default assets:

```
setup_workspace() → configure_llm() → configure_web_tools() → copy_default_assets() → configure_messagebus()
```

### User Flow

1. Checkbox prompt: "Select web tools to enable:"
   - `websearch (Brave Search API)`
   - `webread (local web scraping)`

2. If `websearch` selected:
   - Prompt: "Brave Search API key:"
   - If empty → warn and skip adding to config
   - If provided → add `websearch` config section

3. If `webread` selected:
   - No additional prompts (uses crawl4ai locally)
   - Add `webread` config section

### New Methods

```python
def configure_web_tools(self) -> None:
    """Prompt user for web search and web read configuration."""
    selected = questionary.checkbox(
        "Select web tools to enable:",
        choices=[
            questionary.Choice("websearch (Brave Search API)", value="websearch"),
            questionary.Choice("webread (local web scraping)", value="webread"),
        ],
    ).ask() or []

    if "websearch" in selected:
        config = self._configure_websearch()
        if config:
            self.state["websearch"] = config

    if "webread" in selected:
        self.state["webread"] = {"provider": "crawl4ai"}


def _configure_websearch(self) -> dict | None:
    """Prompt for web search configuration."""
    api_key = questionary.text("Brave Search API key:").ask()

    if not api_key:
        console = Console()
        console.print("[yellow]API key is required for web search. Skipping websearch config.[/yellow]")
        return None

    return {
        "provider": "brave",
        "api_key": api_key,
    }
```

### Config Output

With both tools enabled:
```yaml
websearch:
  provider: brave
  api_key: xxx
webread:
  provider: crawl4ai
```

If skipped, sections are absent from config.

## Edge Cases

| Scenario | Behavior |
|----------|----------|
| No selection | No web tools in config, continue silently |
| Empty API key | Warn and skip websearch, user can add manually later |
| Both selected | Configure both independently |

## Testing

| Test | Description |
|------|-------------|
| `test_configure_web_tools_none` | User selects nothing |
| `test_configure_web_tools_websearch_only` | User selects websearch with valid key |
| `test_configure_web_tools_websearch_empty_key` | User selects websearch but provides empty key |
| `test_configure_web_tools_webread_only` | User selects webread |
| `test_configure_web_tools_both` | User selects both |

## Files Changed

| File | Change |
|------|--------|
| `src/picklebot/cli/onboarding.py` | Add `configure_web_tools()` and `_configure_websearch()` methods |
| `tests/cli/test_onboarding.py` | Add 5 new test cases |
