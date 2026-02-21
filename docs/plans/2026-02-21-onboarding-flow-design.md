# Onboarding Flow Design

**Date:** 2026-02-21
**Status:** Approved

## Overview

Add an interactive onboarding flow to populate config and workspace for new pickle-bot installations.

## Entry Points & Triggers

### 1. `picklebot init` command
Explicit command for initial setup or re-configuration:
```bash
uv run picklebot init
```

### 2. Auto-detection on config load failure
When `Config.load()` raises `FileNotFoundError`:
- Prompt: "No config found. Run onboarding? [Y/n]"
- If user declines, exit with instructions to run `picklebot init`

**Files to modify:**
- `src/picklebot/cli/main.py` — Add `init` command, modify `load_config_callback`
- `src/picklebot/cli/onboarding.py` — New file for onboarding logic

## Onboarding Flow Steps

### Step 1: Welcome & Workspace
- Display welcome message
- Confirm/create workspace directory (`~/.pickle-bot/` by default)
- Create required subdirectories: `agents/`, `skills/`, `crons/`, `memories/`, `.history/`, `.logs/`

### Step 2: LLM Configuration
- Prompt for provider (options: openai, anthropic, zai, etc.)
- Prompt for model name (free text, with examples)
- Prompt for API key (masked input)
- Optional: API base URL (skip for standard providers)

### Step 3: MessageBus Configuration
- Multi-select: "Select messaging platforms to enable:" (Telegram, Discord, None)
- For each selected platform:
  - Bot token (required)
  - Allowed user IDs (optional, comma-separated, skip for open access)
  - Default chat/channel ID (optional)

### Step 4: Complete
- Write configuration to `config.user.yaml`
- Print: "Configuration saved to ~/.pickle-bot/config.user.yaml"
- Print: "Edit this file to make changes."
- Done.

## Code Organization

```
src/picklebot/cli/
├── main.py           # Add `init` command, modify config callback
├── onboarding.py     # New: OnboardingWizard class + steps
└── ...

src/picklebot/cli/onboarding.py:
├── OnboardingWizard class
│   ├── run() -> None           # Main entry point
│   ├── setup_workspace()       # Create directories
│   ├── configure_llm()         # LLM prompts
│   ├── configure_messagebus()  # Platform selection + details
│   └── save_config()           # Write YAML files
```

**Dependencies:**
- Add `questionary` for interactive prompts

**Design decisions:**
- Wizard state stored in a dict, converted to YAML at end
- Reuse existing `Config` Pydantic models for validation before saving
- Separate `init` command from auto-detection logic

## Error Handling & Validation

**Input validation:**
- API key: Non-empty string (no format validation, providers vary)
- Bot token: Non-empty string
- User IDs: Comma-separated integers, validate format
- Model name: Non-empty string

**Error recovery:**
- Invalid input → show error, re-prompt same question
- File write failure → print error with path, exit code 1
- User cancels (Ctrl+C) → graceful exit, no partial config written

**Validation before save:**
- Build config dict from collected inputs
- Pass through Pydantic `Config` model validation
- If validation fails, show specific error and re-prompt affected section

**Idempotency:**
- Re-running `picklebot init` overwrites existing `config.user.yaml`
- Always preserves/creates `config.system.yaml` defaults

## Testing Strategy

**Unit tests for `OnboardingWizard`:**
- Mock `questionary` prompts to test each step in isolation
- Test validation logic (user ID parsing, required fields)
- Test config dict generation from wizard state

**Integration tests:**
- Test full onboarding flow with mocked prompts
- Verify correct YAML output structure
- Test auto-detection trigger when config missing

**Test files:**
```
tests/cli/
├── test_onboarding.py       # Unit tests for wizard steps
└── test_main.py             # Add tests for init command + auto-detection
```

**Key test cases:**
- Fresh install → complete onboarding → valid config
- Re-run init → overwrites existing config
- Skip optional fields → config still valid
- Cancel mid-flow → no partial config written
- Invalid inputs → re-prompted, eventually succeed
