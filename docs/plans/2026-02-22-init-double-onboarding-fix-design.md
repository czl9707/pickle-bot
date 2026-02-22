# Fix Double Onboarding for `init` Command

**Date:** 2026-02-22
**Status:** Approved

## Problem

When running `picklebot init` with no existing config, the onboarding wizard runs twice:
1. The `load_config_callback` detects missing config and offers to run onboarding
2. The `init` command itself runs the onboarding wizard

## Solution

Modify `load_config_callback` in `src/picklebot/cli/main.py` to:
1. Skip config-missing detection when the invoked command is `init`
2. Exit with instructions instead of offering inline onboarding for other commands

## Changes

### `src/picklebot/cli/main.py`

Update `load_config_callback`:

```python
def load_config_callback(ctx: typer.Context, workspace: str):
    """Load configuration and store it in the context."""
    workspace_path = Path(workspace)
    config_file = workspace_path / "config.user.yaml"

    # Skip config check for init command - it handles its own setup
    if ctx.invoked_subcommand == "init":
        ctx.ensure_object(dict)
        ctx.obj["workspace"] = workspace_path
        return

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

Update `init` command to use workspace from context:

```python
@app.command()
def init(ctx: typer.Context) -> None:
    """Initialize pickle-bot configuration with interactive onboarding."""
    workspace = ctx.obj.get("workspace", Path.home() / ".pickle-bot")
    wizard = OnboardingWizard(workspace=workspace)
    wizard.run()
```

## Behavior Summary

| Scenario | Before | After |
|----------|--------|-------|
| `picklebot init` (no config) | Wizard runs twice | Wizard runs once |
| `picklebot init` (config exists) | Wizard runs twice | Wizard runs once, overwrites |
| `picklebot chat` (no config) | Prompts "Run onboarding now? [Y/n]" | Prints message, exits with code 1 |

## Testing

Update `tests/cli/test_main.py`:
- Remove test for inline onboarding prompt (no longer offered)
- Add test for exit with instructions when config missing
- Add test for `init` command skipping callback check
