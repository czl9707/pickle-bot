# MessageBus to Channel Rename - Design Document

**Date:** 2026-03-05
**Status:** Approved
**Scope:** Comprehensive rename of MessageBus terminology to Channel

## Overview

### Goal
Rename all instances of "MessageBus" terminology to "Channel" throughout the codebase to make the concept clearer and more accessible.

### Motivation
- **Accessibility:** "MessageBus" is overly technical/architectural
- **Clarity:** "Channels" better describes the concept (platforms like Telegram, Discord, CLI)
- **Industry alignment:** Common terminology in messaging systems
- **Consistency:** Uniform naming across codebase

### Scope

**Includes:**
- All source code in `src/picklebot/`
- All test code in `tests/`
- All documentation in `docs/`
- Configuration schema and examples
- Variable/function/class names
- File names and directory names
- Comments and docstrings

**Excludes:**
- Discord's internal use of "channel" (kept as-is for Discord-specific context)
- `.mypy_cache/`, `__pycache__/`, and other generated files
- `.worktrees/` directory (separate worktrees)

## Complete Naming Mappings

### Class Names
- `MessageBus` → `Channel`
- `TelegramBus` → `TelegramChannel`
- `DiscordBus` → `DiscordChannel`
- `MessageBusWorker` → `ChannelWorker`
- `MessageBusConfig` → `ChannelConfig`

### Directory & File Names
- `src/picklebot/messagebus/` → `src/picklebot/channel/`
- `messagebus_worker.py` → `channel_worker.py`
- `telegram_bus.py` → `telegram_channel.py`
- `discord_bus.py` → `discord_channel.py`
- `base.py` (no change)
- `docs/messagebus-setup.md` → `docs/channel-setup.md`
- `tests/messagebus/` → `tests/channel/`
- `test_messagebus_worker.py` → `test_channel_worker.py`
- `test_telegram_bus.py` → `test_telegram_channel.py`
- `test_discord_bus.py` → `test_discord_channel.py`

### Variable & Attribute Names
- `messagebus_buses` → `channels` (in SharedContext)
- `messagebus` → `channels` (config field)

### Config Keys
- `messagebus:` → `channels:` (in YAML configs)
- `messagebus.telegram` → `channels.telegram`
- `messagebus.discord` → `channels.discord`

### Import Statements
- `from picklebot.messagebus` → `from picklebot.channel`
- `from picklebot.messagebus.base import MessageBus` → `from picklebot.channel.base import Channel`
- All related imports updated accordingly

### Documentation & Comments
- All occurrences of "MessageBus", "message bus", "messagebus" → "Channel", "channel"

## Execution Plan

### Strategy
Automated bulk find-replace with systematic phases and comprehensive verification.

### Phase 1: Directory & File Structure
1. Rename `src/picklebot/messagebus/` → `src/picklebot/channel/`
2. Rename files inside:
   - `telegram_bus.py` → `telegram_channel.py`
   - `discord_bus.py` → `discord_channel.py`
   - `messagebus_worker.py` → `channel_worker.py`
3. Rename `docs/messagebus-setup.md` → `docs/channel-setup.md`
4. Rename test directory `tests/messagebus/` → `tests/channel/`
5. Rename test files:
   - `test_messagebus_worker.py` → `test_channel_worker.py`
   - `test_telegram_bus.py` → `test_telegram_channel.py`
   - `test_discord_bus.py` → `test_discord_channel.py`

### Phase 2: Core Class Renames
1. Update `src/picklebot/channel/base.py`:
   - `class MessageBus` → `class Channel`
2. Update `src/picklebot/channel/telegram_channel.py`:
   - `class TelegramBus` → `class TelegramChannel`
3. Update `src/picklebot/channel/discord_channel.py`:
   - `class DiscordBus` → `class DiscordChannel`
4. Update `src/picklebot/channel/__init__.py`:
   - Update all exports and imports

### Phase 3: Worker & Context Updates
1. Update `src/picklebot/server/channel_worker.py`:
   - `class MessageBusWorker` → `class ChannelWorker`
   - Update all references to `MessageBus`/`messagebus`
2. Update `src/picklebot/core/context.py`:
   - `messagebus_buses` → `channels`
   - Update imports

### Phase 4: Configuration Schema
1. Update `src/picklebot/utils/config.py`:
   - `class MessageBusConfig` → `class ChannelConfig`
   - Update field names and references
2. Update all config loading/validation code

### Phase 5: Find-Replace in Source Code
1. Search and replace in all `src/picklebot/**/*.py`:
   - `MessageBus` → `Channel`
   - `TelegramBus` → `TelegramChannel`
   - `DiscordBus` → `DiscordChannel`
   - `MessageBusWorker` → `ChannelWorker`
   - `MessageBusConfig` → `ChannelConfig`
   - `messagebus` → `channel` (with context awareness)
   - Import paths: `picklebot.messagebus` → `picklebot.channel`

### Phase 6: Find-Replace in Tests
1. Same replacements in all `tests/**/*.py` files
2. Update test fixtures and mocks

### Phase 7: Documentation Updates
1. Update all markdown files in `docs/`:
   - Architecture docs
   - Configuration docs
   - Feature docs
   - All design docs in `docs/plans/`
2. Update `CLAUDE.md`
3. Update code comments and docstrings

### Phase 8: Configuration Files
1. Update any example config files
2. Update onboarding wizard if it references messagebus

### Phase 9: Verification
1. Run `uv run black . && uv run ruff check .`
2. Run `uv run pytest` - all tests must pass
3. Manual verification:
   - Check for any remaining "messagebus" strings
   - Verify imports resolve correctly
   - Test server startup

## Verification Strategy

### Pre-Rename Safety
1. Clean git state - ensure no uncommitted changes
2. Current branch - work on main or create feature branch
3. Document current state - note test results before changes

### During Rename Verification

**After Phases 1-4 (Core renames):**
```bash
# Check imports resolve
uv run python -c "from picklebot.channel import Channel"
uv run python -c "from picklebot.channel import TelegramChannel, DiscordChannel"
```

**After Phase 5-6 (Source & tests):**
```bash
# Run tests to catch breakages early
uv run pytest tests/channel/
uv run pytest tests/server/test_channel_worker.py
```

### Final Verification Checklist

1. **Code quality:**
   ```bash
   uv run black . && uv run ruff check .
   ```

2. **Full test suite:**
   ```bash
   uv run pytest
   ```
   - All tests must pass
   - No import errors

3. **Search for remaining instances:**
   ```bash
   # Check for any remaining "messagebus" (excluding cache/worktrees)
   rg -i "messagebus" src/ tests/ docs/ --type-add 'exclude:*.{pyc,pyo}' -t py -t md
   ```

4. **Manual smoke test:**
   ```bash
   # Test CLI
   uv run picklebot --help

   # Test server startup (if possible)
   uv run picklebot server
   ```

### Rollback Plan
- If tests fail: Fix issues incrementally in same commit
- If major issues: `git reset --hard HEAD` to revert all changes
- Work on feature branch: Can always delete and start over

### Expected Test Failures
None expected - this is purely a rename with no logic changes.

## Expected Impact

### Files Modified
- **35+ files** will be modified
- **1 directory** renamed (`messagebus/` → `channel/`)
- **6 core classes** renamed
- **All configs, docs, and tests** updated

### Functional Impact
- **Zero logic changes** - pure rename
- All functionality preserved
- No breaking changes for end users (internal rename only)

### Timeline
- Estimated: 1-2 hours for complete rename + verification
- Tests should pass immediately after rename (no logic changes)

## Success Criteria

- ✅ All "messagebus" references replaced with "channel"
- ✅ All tests pass
- ✅ Code formats cleanly (black + ruff)
- ✅ No import errors
- ✅ Server starts successfully
- ✅ Documentation updated consistently

## Notes

- Discord's internal use of "channel" (e.g., `channel_id`, `message.channel`) will be preserved as it's Discord-specific and clear in context
- This rename applies only to the platform abstraction layer, not platform-specific concepts
