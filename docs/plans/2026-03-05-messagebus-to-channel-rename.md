# Channel to Channel Rename Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Rename all "Channel" terminology to "Channel" across the entire pickle-bot codebase.

**Architecture:** Systematic file-by-file rename with test verification at each phase. Directory structure changes first, then class renames, then config updates, followed by documentation and final verification.

**Tech Stack:** Python, pytest, black, ruff, git

**Design Doc:** [2026-03-05-channels-to-channel-rename-design.md](./2026-03-05-channels-to-channel-rename-design.md)

---

## Phase 1: Directory Structure Renames

### Task 1: Rename channels directory to channel

**Files:**
- Move: `src/picklebot/channels/` → `src/picklebot/channel/`

**Step 1: Rename the directory**

```bash
git mv src/picklebot/channels src/picklebot/channel
```

**Step 2: Verify directory structure**

Run: `ls -la src/picklebot/channel/`
Expected: See `base.py`, `telegram_bus.py`, `discord_bus.py`, `__init__.py`

**Step 3: Commit**

```bash
git add -A
git commit -m "refactor: rename channels directory to channel"
```

### Task 2: Rename files inside channel directory

**Files:**
- Move: `src/picklebot/channel/telegram_bus.py` → `src/picklebot/channel/telegram_channel.py`
- Move: `src/picklebot/channel/discord_bus.py` → `src/picklebot/channel/discord_channel.py`

**Step 1: Rename telegram_bus.py**

```bash
git mv src/picklebot/channel/telegram_bus.py src/picklebot/channel/telegram_channel.py
```

**Step 2: Rename discord_bus.py**

```bash
git mv src/picklebot/channel/discord_bus.py src/picklebot/channel/discord_channel.py
```

**Step 3: Verify files renamed**

Run: `ls -la src/picklebot/channel/`
Expected: See `telegram_channel.py` and `discord_channel.py`

**Step 4: Commit**

```bash
git add -A
git commit -m "refactor: rename telegram_bus and discord_bus files"
```

### Task 3: Rename channels_worker.py to channel_worker.py

**Files:**
- Move: `src/picklebot/server/channels_worker.py` → `src/picklebot/server/channel_worker.py`

**Step 1: Rename the worker file**

```bash
git mv src/picklebot/server/channels_worker.py src/picklebot/server/channel_worker.py
```

**Step 2: Verify file renamed**

Run: `ls -la src/picklebot/server/channel_worker.py`
Expected: File exists

**Step 3: Commit**

```bash
git add -A
git commit -m "refactor: rename channels_worker to channel_worker"
```

### Task 4: Rename test directory structure

**Files:**
- Move: `tests/channels/` → `tests/channel/`
- Move: `tests/channels/test_base.py` → `tests/channel/test_base.py` (auto-moved with dir)
- Move: `tests/channels/test_telegram_bus.py` → `tests/channel/test_telegram_channel.py`
- Move: `tests/channels/test_discord_bus.py` → `tests/channel/test_discord_channel.py`
- Move: `tests/server/test_channels_worker.py` → `tests/server/test_channel_worker.py`

**Step 1: Rename tests/channels directory**

```bash
git mv tests/channels tests/channel
```

**Step 2: Rename test_telegram_bus.py**

```bash
git mv tests/channel/test_telegram_bus.py tests/channel/test_telegram_channel.py
```

**Step 3: Rename test_discord_bus.py**

```bash
git mv tests/channel/test_discord_bus.py tests/channel/test_discord_channel.py
```

**Step 4: Rename test_channels_worker.py**

```bash
git mv tests/server/test_channels_worker.py tests/server/test_channel_worker.py
```

**Step 5: Verify all test files renamed**

Run: `ls -la tests/channel/ && ls -la tests/server/test_channel_worker.py`
Expected: See renamed files

**Step 6: Commit**

```bash
git add -A
git commit -m "refactor: rename test files to match channel naming"
```

### Task 5: Rename documentation file

**Files:**
- Move: `docs/channels-setup.md` → `docs/channel-setup.md`

**Step 1: Rename the doc file**

```bash
git mv docs/channels-setup.md docs/channel-setup.md
```

**Step 2: Verify file renamed**

Run: `ls -la docs/channel-setup.md`
Expected: File exists

**Step 3: Commit**

```bash
git add -A
git commit -m "refactor: rename channels-setup.md to channel-setup.md"
```

---

## Phase 2: Core Class Renames in channel/base.py

### Task 6: Rename Channel class to Channel

**Files:**
- Modify: `src/picklebot/channel/base.py:13`

**Step 1: Read the current file**

Run: `cat src/picklebot/channel/base.py`
Note the current class definition

**Step 2: Update class name and docstring**

Change line 13 from:
```python
class Channel(ABC, Generic[T]):
    """Abstract base for messaging platforms with EventSource-based context."""
```

To:
```python
class Channel(ABC, Generic[T]):
    """Abstract base for messaging platforms with EventSource-based context."""
```

**Step 3: Update method docstrings**

Update line 70-72 from:
```python
    @staticmethod
    def from_config(config: Config) -> list["Channel[Any]"]:
        """
        Create message bus instances from configuration.
```

To:
```python
    @staticmethod
    def from_config(config: Config) -> list["Channel[Any]"]:
        """
        Create channel instances from configuration.
```

Update line 84 from:
```python
        buses: list["Channel[Any]"] = []
```

To:
```python
        buses: list["Channel[Any]"] = []
```

**Step 4: Verify syntax is correct**

Run: `python -m py_compile src/picklebot/channel/base.py`
Expected: No errors

**Step 5: Commit**

```bash
git add src/picklebot/channel/base.py
git commit -m "refactor: rename Channel class to Channel"
```

### Task 7: Update channel/__init__.py exports

**Files:**
- Modify: `src/picklebot/channel/__init__.py`

**Step 1: Read current file**

Run: `cat src/picklebot/channel/__init__.py`

**Step 2: Update imports and exports**

Change:
```python
"""Channel implementations for different platforms."""

from picklebot.channels.base import Channel
from picklebot.channels.telegram_bus import TelegramBus
from picklebot.channels.discord_bus import DiscordBus

__all__ = ["Channel", "TelegramBus", "DiscordBus"]
```

To:
```python
"""Channel implementations for different platforms."""

from picklebot.channel.base import Channel
from picklebot.channel.telegram_channel import TelegramChannel
from picklebot.channel.discord_channel import DiscordChannel

__all__ = ["Channel", "TelegramChannel", "DiscordChannel"]
```

**Step 3: Verify syntax**

Run: `python -m py_compile src/picklebot/channel/__init__.py`
Expected: No errors

**Step 4: Commit**

```bash
git add src/picklebot/channel/__init__.py
git commit -m "refactor: update channel __init__.py exports"
```

### Task 8: Rename TelegramBus class to TelegramChannel

**Files:**
- Modify: `src/picklebot/channel/telegram_channel.py`

**Step 1: Read the file to find class definition**

Run: `head -20 src/picklebot/channel/telegram_channel.py`

**Step 2: Rename the class**

Find and replace all occurrences:
- `class TelegramBus` → `class TelegramChannel`
- `TelegramBus` (in type hints and references) → `TelegramChannel`

**Step 3: Update docstrings**

Change any docstrings that reference "TelegramBus" or "Telegram bus" to "TelegramChannel" or "Telegram channel"

**Step 4: Verify syntax**

Run: `python -m py_compile src/picklebot/channel/telegram_channel.py`
Expected: No errors

**Step 5: Commit**

```bash
git add src/picklebot/channel/telegram_channel.py
git commit -m "refactor: rename TelegramBus to TelegramChannel"
```

### Task 9: Rename DiscordBus class to DiscordChannel

**Files:**
- Modify: `src/picklebot/channel/discord_channel.py`

**Step 1: Read the file**

Run: `head -20 src/picklebot/channel/discord_channel.py`

**Step 2: Rename the class**

Find and replace all occurrences:
- `class DiscordBus` → `class DiscordChannel`
- `DiscordBus` → `DiscordChannel`

**Step 3: Update docstrings**

Change any references to "DiscordBus" or "Discord bus" to "DiscordChannel" or "Discord channel"

**Step 4: Verify syntax**

Run: `python -m py_compile src/picklebot/channel/discord_channel.py`
Expected: No errors

**Step 5: Commit**

```bash
git add src/picklebot/channel/discord_channel.py
git commit -m "refactor: rename DiscordBus to DiscordChannel"
```

---

## Phase 3: Worker Class Rename

### Task 10: Rename ChannelWorker to ChannelWorker

**Files:**
- Modify: `src/picklebot/server/channel_worker.py`

**Step 1: Read the file**

Run: `cat src/picklebot/server/channel_worker.py`

**Step 2: Update class name and imports**

Change:
```python
from picklebot.channels.base import Channel
```

To:
```python
from picklebot.channel.base import Channel
```

Change:
```python
class ChannelWorker(Worker):
    """Ingests messages from platforms, publishes INBOUND events to EventBus."""
```

To:
```python
class ChannelWorker(Worker):
    """Ingests messages from platforms, publishes INBOUND events to EventBus."""
```

**Step 3: Update variable names**

Find: `self.buses` and references
Update docstrings and log messages:
- `ChannelWorker started` → `ChannelWorker started`

**Step 4: Verify syntax**

Run: `python -m py_compile src/picklebot/server/channel_worker.py`
Expected: No errors

**Step 5: Commit**

```bash
git add src/picklebot/server/channel_worker.py
git commit -m "refactor: rename ChannelWorker to ChannelWorker"
```

### Task 11: Update server/__init__.py exports

**Files:**
- Modify: `src/picklebot/server/__init__.py`

**Step 1: Read current file**

Run: `cat src/picklebot/server/__init__.py`

**Step 2: Update import**

Change:
```python
from .channels_worker import ChannelWorker
```

To:
```python
from .channel_worker import ChannelWorker
```

**Step 3: Verify syntax**

Run: `python -m py_compile src/picklebot/server/__init__.py`
Expected: No errors

**Step 4: Commit**

```bash
git add src/picklebot/server/__init__.py
git commit -m "refactor: update server exports for ChannelWorker"
```

---

## Phase 4: Configuration Schema Updates

### Task 12: Rename ChannelConfig to ChannelConfig

**Files:**
- Modify: `src/picklebot/utils/config.py:60-66`

**Step 1: Read the config section**

Run: `sed -n '60,66p' src/picklebot/utils/config.py`

**Step 2: Update class name**

Change:
```python
class ChannelConfig(BaseModel):
    """Channel configuration."""

    enabled: bool = False
    telegram: TelegramConfig | None = None
    discord: DiscordConfig | None = None
```

To:
```python
class ChannelConfig(BaseModel):
    """Channel configuration."""

    enabled: bool = False
    telegram: TelegramConfig | None = None
    discord: DiscordConfig | None = None
```

**Step 3: Update field name in Config class**

Find line 108 and change:
```python
    channels: ChannelConfig = Field(default_factory=ChannelConfig)
```

To:
```python
    channels: ChannelConfig = Field(default_factory=ChannelConfig)
```

**Step 4: Search for other references**

Run: `rg "ChannelConfig|\.channels" src/picklebot/utils/config.py`
Review and update any additional references

**Step 5: Verify syntax**

Run: `python -m py_compile src/picklebot/utils/config.py`
Expected: No errors

**Step 6: Commit**

```bash
git add src/picklebot/utils/config.py
git commit -m "refactor: rename ChannelConfig to ChannelConfig"
```

---

## Phase 5: Context Updates

### Task 13: Update SharedContext attribute name

**Files:**
- Modify: `src/picklebot/core/context.py:24,41,43`

**Step 1: Read context file**

Run: `cat src/picklebot/core/context.py`

**Step 2: Update import**

Change line 11:
```python
from picklebot.channels.base import Channel
```

To:
```python
from picklebot.channel.base import Channel
```

**Step 3: Update type annotation**

Change line 24:
```python
    channels_buses: list[Channel[Any]]
```

To:
```python
    channels: list[Channel[Any]]
```

**Step 4: Update attribute assignment**

Change lines 41-43:
```python
            self.channels_buses = buses
        else:
            self.channels_buses = Channel.from_config(config)
```

To:
```python
            self.channels = buses
        else:
            self.channels = Channel.from_config(config)
```

**Step 5: Verify syntax**

Run: `python -m py_compile src/picklebot/core/context.py`
Expected: No errors

**Step 6: Commit**

```bash
git add src/picklebot/core/context.py
git commit -m "refactor: rename channels_buses to channels in SharedContext"
```

---

## Phase 6: Bulk Find-Replace in Source Code

### Task 14: Find and replace Channel references in src/

**Files:**
- All Python files in `src/picklebot/`

**Step 1: Find all Channel references**

Run: `rg "Channel|ChannelWorker|ChannelConfig" src/picklebot/ --type py -l`
Note: This will show which files need updating

**Step 2: Perform systematic replacements**

For each file found, replace:
- `Channel` → `Channel`
- `TelegramBus` → `TelegramChannel`
- `DiscordBus` → `DiscordChannel`
- `ChannelWorker` → `ChannelWorker`
- `ChannelConfig` → `ChannelConfig`
- `channels_buses` → `channels`
- `picklebot.channels` → `picklebot.channel`

**Step 3: Run syntax check on all modified files**

Run: `python -m py_compile src/picklebot/**/*.py 2>&1 | head -20`
Expected: No errors (or only expected errors from files not yet updated)

**Step 4: Run specific tests**

Run: `uv run pytest tests/channel/ -v`
Expected: Tests may fail due to import issues, but syntax should be valid

**Step 5: Commit**

```bash
git add src/picklebot/
git commit -m "refactor: replace Channel references with Channel in source code"
```

### Task 15: Update delivery_worker.py references

**Files:**
- Modify: `src/picklebot/server/delivery_worker.py`

**Step 1: Find channels references**

Run: `rg "channels|Channel" src/picklebot/server/delivery_worker.py`

**Step 2: Update imports and references**

Replace any occurrences of:
- `from picklebot.channels` → `from picklebot.channel`
- `Channel` → `Channel`

**Step 3: Verify syntax**

Run: `python -m py_compile src/picklebot/server/delivery_worker.py`
Expected: No errors

**Step 4: Commit**

```bash
git add src/picklebot/server/delivery_worker.py
git commit -m "refactor: update delivery_worker Channel references"
```

---

## Phase 7: Test File Updates

### Task 16: Update test imports and class names

**Files:**
- All test files in `tests/`

**Step 1: Find test files with Channel references**

Run: `rg "Channel|TelegramBus|DiscordBus|ChannelWorker" tests/ --type py -l`

**Step 2: Update each test file**

For each file, replace:
- `from picklebot.channels` → `from picklebot.channel`
- `Channel` → `Channel`
- `TelegramBus` → `TelegramChannel`
- `DiscordBus` → `DiscordChannel`
- `ChannelWorker` → `ChannelWorker`
- `test_telegram_bus` → `test_telegram_channel`
- `test_discord_bus` → `test_discord_channel`
- `test_channels_worker` → `test_channel_worker`

**Step 3: Run channel tests**

Run: `uv run pytest tests/channel/ -v`
Expected: Some tests may still fail, but imports should resolve

**Step 4: Run server tests**

Run: `uv run pytest tests/server/test_channel_worker.py -v`
Expected: Tests may fail but should import correctly

**Step 5: Commit**

```bash
git add tests/
git commit -m "refactor: update test files for Channel naming"
```

### Task 17: Update test fixtures and mocks

**Files:**
- `tests/conftest.py` and other fixture files

**Step 1: Find fixture references**

Run: `rg "channels|Channel" tests/conftest.py`

**Step 2: Update fixtures**

Replace:
- `channels` → `channels` in fixture names and config
- `Channel` → `Channel` in type hints

**Step 3: Verify tests still work**

Run: `uv run pytest tests/ -k "channel or Channel" -v`
Expected: Tests run without import errors

**Step 4: Commit**

```bash
git add tests/conftest.py
git commit -m "refactor: update test fixtures for Channel naming"
```

---

## Phase 8: Documentation Updates

### Task 18: Update channel-setup.md

**Files:**
- Modify: `docs/channel-setup.md`

**Step 1: Find Channel references**

Run: `rg "channels|Channel|Channel" docs/channel-setup.md -i`

**Step 2: Update all references**

Replace:
- `Channel` → `Channel`
- `channels` → `channel` (in config examples)
- `Channel` → `Channel`

**Step 3: Verify file reads correctly**

Run: `cat docs/channel-setup.md`
Check that it reads naturally

**Step 4: Commit**

```bash
git add docs/channel-setup.md
git commit -m "docs: update channel-setup.md terminology"
```

### Task 19: Update configuration.md

**Files:**
- Modify: `docs/configuration.md`

**Step 1: Find all references**

Run: `rg "channels|Channel|Channel" docs/configuration.md -i -C 2`

**Step 2: Update terminology**

Replace throughout:
- `Channel` → `Channel`
- `channels:` → `channels:` in config examples
- `Channel` → `Channel` in prose

**Step 3: Verify examples are correct**

Check that YAML examples show:
```yaml
channels:
  enabled: true
  telegram:
    ...
```

**Step 4: Commit**

```bash
git add docs/configuration.md
git commit -m "docs: update configuration.md for Channel terminology"
```

### Task 20: Update architecture.md

**Files:**
- Modify: `docs/architecture.md`

**Step 1: Find references**

Run: `rg "channels|Channel" docs/architecture.md -i -C 2`

**Step 2: Update all occurrences**

Replace:
- `Channel` → `Channel`
- `channels/` → `channel/`
- `ChannelWorker` → `ChannelWorker`

**Step 3: Commit**

```bash
git add docs/architecture.md
git commit -m "docs: update architecture.md for Channel terminology"
```

### Task 21: Update features.md

**Files:**
- Modify: `docs/features.md`

**Step 1: Find references**

Run: `rg "channels|Channel" docs/features.md -i`

**Step 2: Update all occurrences**

Replace Channel terminology with Channel

**Step 3: Commit**

```bash
git add docs/features.md
git commit -m "docs: update features.md for Channel terminology"
```

### Task 22: Update CLAUDE.md

**Files:**
- Modify: `CLAUDE.md`

**Step 1: Find references**

Run: `rg "channels|Channel" CLAUDE.md -i`

**Step 2: Update all occurrences**

Replace:
- `ChannelWorker` → `ChannelWorker`
- `channels/` → `channel/`
- `Channel` → `Channel`

**Step 3: Commit**

```bash
git add CLAUDE.md
git commit -m "docs: update CLAUDE.md for Channel terminology"
```

### Task 23: Update design plan documents

**Files:**
- All markdown files in `docs/plans/`

**Step 1: Find affected plan docs**

Run: `rg "channels|Channel" docs/plans/*.md -l`

**Step 2: Update each document**

For each file found, replace Channel terminology with Channel

**Step 3: Commit**

```bash
git add docs/plans/
git commit -m "docs: update design documents for Channel terminology"
```

---

## Phase 9: Onboarding and CLI Updates

### Task 24: Update onboarding wizard

**Files:**
- Modify: `src/picklebot/cli/onboarding/steps.py`
- Modify: `src/picklebot/cli/onboarding/wizard.py`

**Step 1: Find Channel references**

Run: `rg "channels|Channel" src/picklebot/cli/onboarding/`

**Step 2: Update references**

Replace:
- `channels` → `channels` (config keys)
- `Channel` → `Channel`

**Step 3: Verify syntax**

Run: `python -m py_compile src/picklebot/cli/onboarding/steps.py`
Run: `python -m py_compile src/picklebot/cli/onboarding/wizard.py`
Expected: No errors

**Step 4: Commit**

```bash
git add src/picklebot/cli/onboarding/
git commit -m "refactor: update onboarding for Channel terminology"
```

### Task 25: Update CLI server command

**Files:**
- Modify: `src/picklebot/cli/server.py`

**Step 1: Find Channel references**

Run: `rg "ChannelWorker|Channel" src/picklebot/cli/server.py`

**Step 2: Update imports and references**

Replace:
- `ChannelWorker` → `ChannelWorker`

**Step 3: Verify syntax**

Run: `python -m py_compile src/picklebot/cli/server.py`
Expected: No errors

**Step 4: Commit**

```bash
git add src/picklebot/cli/server.py
git commit -m "refactor: update CLI server command for ChannelWorker"
```

---

## Phase 10: Final Verification

### Task 26: Run code formatters

**Files:**
- All Python files

**Step 1: Run black formatter**

Run: `uv run black .`
Expected: Files formatted successfully

**Step 2: Run ruff linter**

Run: `uv run ruff check .`
Expected: No errors (or only pre-existing warnings)

**Step 3: Commit formatting changes**

```bash
git add -A
git commit -m "style: apply black formatting after Channel rename"
```

### Task 27: Run full test suite

**Files:**
- All test files

**Step 1: Run all tests**

Run: `uv run pytest`
Expected: All tests pass

**Step 2: If tests fail, investigate**

For each failure:
1. Check the error message
2. Verify the rename was complete in that file
3. Fix any missed references
4. Re-run tests

**Step 3: Verify test count matches**

Compare test count before and after - should be identical

### Task 28: Search for remaining Channel references

**Files:**
- All source, test, and doc files

**Step 1: Search for remaining occurrences**

Run: `rg -i "channels" src/ tests/ docs/ --type py --type md -C 2`

**Step 2: Review any findings**

Expected: Only references in:
- Comments about the rename itself
- Discord's internal `channel` usage (allowed)
- Generated files (.mypy_cache, __pycache__, .worktrees)

**Step 3: If references found in source/test/docs, fix them**

### Task 29: Manual verification tests

**Files:**
- Various

**Step 1: Test CLI help**

Run: `uv run picklebot --help`
Expected: Command runs successfully

**Step 2: Test server import**

Run: `uv run python -c "from picklebot.server import ChannelWorker; print('OK')"`
Expected: Prints "OK"

**Step 3: Test channel imports**

Run: `uv run python -c "from picklebot.channel import Channel, TelegramChannel, DiscordChannel; print('OK')"`
Expected: Prints "OK"

**Step 4: Test config loading**

Run: `uv run python -c "from picklebot.utils.config import Config; print('OK')"`
Expected: Prints "OK"

### Task 30: Final commit

**Step 1: Review all changes**

Run: `git log --oneline -20`
Review commits to ensure logical progression

**Step 2: Check for uncommitted changes**

Run: `git status`
Expected: Clean working tree

**Step 3: Create final summary commit (if needed)**

If there are any remaining changes:
```bash
git add -A
git commit -m "refactor: complete Channel to Channel rename"
```

---

## Verification Checklist

After completing all tasks, verify:

- [ ] Directory `src/picklebot/channels/` no longer exists
- [ ] Directory `src/picklebot/channel/` exists with all files
- [ ] All test files renamed correctly
- [ ] All classes renamed (Channel, TelegramChannel, DiscordChannel, ChannelWorker, ChannelConfig)
- [ ] All imports updated from `picklebot.channels` to `picklebot.channel`
- [ ] Config schema uses `channels:` instead of `channels:`
- [ ] Context attribute is `context.channels` not `context.channels_buses`
- [ ] All documentation updated
- [ ] All tests pass
- [ ] Code formats cleanly with black and ruff
- [ ] No remaining "Channel" references in src/, tests/, or docs/
- [ ] Server can start successfully
- [ ] CLI commands work

## Rollback Instructions

If major issues arise:

1. **Soft rollback (if on feature branch):**
   ```bash
   git checkout main
   git branch -D feature/channels-to-channel-rename
   ```

2. **Hard rollback (if on main):**
   ```bash
   git reset --hard dbe00fa  # Last commit before rename started
   ```

3. **Selective rollback:**
   ```bash
   git revert <commit-sha>  # Revert specific commits
   ```

## Notes

- This is a pure rename refactor - no logic changes
- Discord's internal use of "channel" (e.g., `channel_id`) is preserved
- All changes should be reversible via git
- Test failures during intermediate steps are expected - only final test run matters
- Commit frequently to enable easy rollback if needed
