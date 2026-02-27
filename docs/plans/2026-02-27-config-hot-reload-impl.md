# Config Hot Reload Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add config hot reload using watchdog to reload `config.user.yaml` without server restart.

**Architecture:** A `ConfigReloader` class manages a watchdog observer that watches `config.user.yaml`. On modification, it calls `Config.reload()` to re-parse and merge the config. Workers pick up changes on next access.

**Tech Stack:** watchdog library for file system events

---

## Task 1: Add watchdog dependency

**Files:**
- Modify: `pyproject.toml:19-34`

**Step 1: Add watchdog to dependencies**

In `pyproject.toml`, add `watchdog` to the dependencies list:

```python
dependencies = [
  "litellm>=1.0.0",
  "typer>=0.12.0",
  "textual>=0.21.0",
  "pydantic>=2.0.0",
  "pyyaml>=6.0",
  "rich>=13.0.0",
  "croniter>=1.0.0",
  "python-telegram-bot>=20.0",
  "discord.py>=2.0",
  "questionary>=2.0.0",
  "fastapi>=0.115.0",
  "uvicorn[standard]>=0.32.0",
  "httpx>=0.27.0",
  "crawl4ai>=0.4.0",
  "watchdog>=5.0.0",  # Add this line
]
```

**Step 2: Sync dependencies**

Run: `uv sync`
Expected: Dependencies resolved, watchdog installed

**Step 3: Commit**

```bash
git add pyproject.toml uv.lock
git commit -m "feat: add watchdog dependency for config hot reload"
```

---

## Task 2: Add reload() method to Config

**Files:**
- Modify: `src/picklebot/utils/config.py:288-`
- Test: `tests/utils/test_config.py`

**Step 1: Write the failing test**

Add to `tests/utils/test_config.py`:

```python
class TestConfigReload:
    """Tests for config hot reload."""

    def test_reload_reads_updated_config(self, tmp_path, llm_config):
        """reload() should re-read config.user.yaml."""
        import yaml

        # Create initial config
        config_file = tmp_path / "config.user.yaml"
        config_file.write_text("llm:\n  provider: openai\n  model: gpt-4\n  api_key: test\n")

        config = Config.load(tmp_path)
        assert config.llm.model == "gpt-4"

        # Modify the file
        config_file.write_text("llm:\n  provider: openai\n  model: gpt-4o\n  api_key: test\n")

        # Reload
        config.reload()
        assert config.llm.model == "gpt-4o"
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/utils/test_config.py::TestConfigReload -v`
Expected: FAIL with "Config has no attribute 'reload'"

**Step 3: Write minimal implementation**

Add to `src/picklebot/utils/config.py`, after the `set_runtime` method (around line 287):

```python
    def reload(self) -> bool:
        """
        Re-read config.user.yaml and merge with runtime.

        Returns:
            True if reload succeeded, False if file not found or invalid
        """
        try:
            user_config = self.workspace / "config.user.yaml"
            runtime_config = self.workspace / "config.runtime.yaml"

            config_data: dict[str, Any] = {"workspace": self.workspace}

            if user_config.exists():
                with open(user_config) as f:
                    user_data = yaml.safe_load(f) or {}
                config_data = self._deep_merge(config_data, user_data)

            if runtime_config.exists():
                with open(runtime_config) as f:
                    runtime_data = yaml.safe_load(f) or {}
                config_data = self._deep_merge(config_data, runtime_data)

            # Create new instance and copy values
            new_config = Config.model_validate(config_data)

            # Update all fields from new config
            for field_name in new_config.model_fields:
                setattr(self, field_name, getattr(new_config, field_name))

            return True
        except Exception:
            return False
```

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/utils/test_config.py::TestConfigReload -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/picklebot/utils/config.py tests/utils/test_config.py
git commit -m "feat(config): add reload() method for hot reload support"
```

---

## Task 3: Add ConfigHandler class

**Files:**
- Modify: `src/picklebot/utils/config.py`
- Test: `tests/utils/test_config.py`

**Step 1: Write the failing test**

Add to `tests/utils/test_config.py`:

```python
class TestConfigHandler:
    """Tests for ConfigHandler file watching."""

    def test_handler_calls_reload_on_modify(self, tmp_path, llm_config):
        """ConfigHandler should call reload when config file changes."""
        from picklebot.utils.config import ConfigHandler
        from watchdog.events import FileModifiedEvent

        # Create config file
        config_file = tmp_path / "config.user.yaml"
        config_file.write_text("llm:\n  provider: openai\n  model: gpt-4\n  api_key: test\n")

        config = Config.load(tmp_path)
        handler = ConfigHandler(config)

        # Modify file
        config_file.write_text("llm:\n  provider: openai\n  model: gpt-4o\n  api_key: test\n")

        # Trigger the handler
        event = FileModifiedEvent(str(config_file))
        handler.on_modified(event)

        assert config.llm.model == "gpt-4o"

    def test_handler_ignores_other_files(self, tmp_path, llm_config):
        """ConfigHandler should ignore non-config files."""
        from picklebot.utils.config import ConfigHandler
        from watchdog.events import FileModifiedEvent

        config_file = tmp_path / "config.user.yaml"
        config_file.write_text("llm:\n  provider: openai\n  model: gpt-4\n  api_key: test\n")

        config = Config.load(tmp_path)
        handler = ConfigHandler(config)

        # Touch a different file
        other_file = tmp_path / "other.yaml"
        other_file.write_text("foo: bar")

        event = FileModifiedEvent(str(other_file))
        handler.on_modified(event)

        # Config should be unchanged
        assert config.llm.model == "gpt-4"
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/utils/test_config.py::TestConfigHandler -v`
Expected: FAIL with "cannot import name 'ConfigHandler'"

**Step 3: Write minimal implementation**

Add to `src/picklebot/utils/config.py`, at the top after imports:

```python
from watchdog.events import FileSystemEventHandler
```

Add to `src/picklebot/utils/config.py`, after the `Config` class (around line 320):

```python
class ConfigHandler(FileSystemEventHandler):
    """Handles config file modification events."""

    def __init__(self, config: Config):
        self._config = config

    def on_modified(self, event):
        """Reload config when config.user.yaml changes."""
        if not event.is_directory and event.src_path.endswith("config.user.yaml"):
            self._config.reload()
```

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/utils/test_config.py::TestConfigHandler -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/picklebot/utils/config.py tests/utils/test_config.py
git commit -m "feat(config): add ConfigHandler for watchdog events"
```

---

## Task 4: Add ConfigReloader class

**Files:**
- Modify: `src/picklebot/utils/config.py`
- Test: `tests/utils/test_config.py`

**Step 1: Write the failing test**

Add to `tests/utils/test_config.py`:

```python
class TestConfigReloader:
    """Tests for ConfigReloader lifecycle."""

    def test_reloader_starts_and_stops_observer(self, tmp_path, llm_config):
        """ConfigReloader should start/stop watchdog observer."""
        from picklebot.utils.config import ConfigReloader

        config_file = tmp_path / "config.user.yaml"
        config_file.write_text("llm:\n  provider: openai\n  model: gpt-4\n  api_key: test\n")

        config = Config.load(tmp_path)
        reloader = ConfigReloader(config)

        # Start should create observer
        reloader.start()
        assert reloader._observer is not None
        assert reloader._observer.is_alive()

        # Stop should clean up
        reloader.stop()
        assert not reloader._observer.is_alive()

    def test_reloader_watches_config_changes(self, tmp_path, llm_config):
        """ConfigReloader should reload config on file change."""
        import time
        from picklebot.utils.config import ConfigReloader

        config_file = tmp_path / "config.user.yaml"
        config_file.write_text("llm:\n  provider: openai\n  model: gpt-4\n  api_key: test\n")

        config = Config.load(tmp_path)
        reloader = ConfigReloader(config)
        reloader.start()

        # Modify file
        config_file.write_text("llm:\n  provider: openai\n  model: gpt-4o\n  api_key: test\n")

        # Wait for event to propagate
        time.sleep(0.5)

        assert config.llm.model == "gpt-4o"

        reloader.stop()
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/utils/test_config.py::TestConfigReloader -v`
Expected: FAIL with "cannot import name 'ConfigReloader'"

**Step 3: Write minimal implementation**

Add to `src/picklebot/utils/config.py`, at the top after imports:

```python
from watchdog.observers import Observer
```

Add to `src/picklebot/utils/config.py`, after the `ConfigHandler` class:

```python
class ConfigReloader:
    """Manages watchdog observer for config hot reload."""

    def __init__(self, config: Config):
        self._config = config
        self._observer: Observer | None = None

    def start(self) -> None:
        """Start watching config file for changes."""
        if self._observer is not None:
            return

        self._observer = Observer()
        handler = ConfigHandler(self._config)
        self._observer.schedule(handler, str(self._config.workspace), recursive=False)
        self._observer.start()

    def stop(self) -> None:
        """Stop watching."""
        if self._observer is not None:
            self._observer.stop()
            self._observer.join()
            self._observer = None
```

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/utils/test_config.py::TestConfigReloader -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/picklebot/utils/config.py tests/utils/test_config.py
git commit -m "feat(config): add ConfigReloader to manage watchdog observer"
```

---

## Task 5: Integrate ConfigReloader into Server

**Files:**
- Modify: `src/picklebot/server/server.py`
- Test: `tests/server/test_server.py`

**Step 1: Write the failing test**

Add to `tests/server/test_server.py`:

```python
def test_server_starts_config_reloader(test_context):
    """Server should start ConfigReloader alongside workers."""
    from unittest.mock import patch

    with patch("picklebot.server.server.ConfigReloader") as mock_reloader:
        mock_instance = mock_reloader.return_value
        server = Server(test_context)

        # Run setup (not full run, just setup)
        server._setup_workers()

        # ConfigReloader should be created and started
        mock_reloader.assert_called_once_with(test_context.config)

        # Cleanup
        import asyncio
        asyncio.get_event_loop().run_until_complete(server._stop_all())
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/server/test_server.py::test_server_starts_config_reloader -v`
Expected: FAIL - mock_reloader not called

**Step 3: Write minimal implementation**

Modify `src/picklebot/server/server.py`:

Add import at top:
```python
from picklebot.utils.config import ConfigReloader
```

Modify `__init__` method:
```python
    def __init__(self, context: "SharedContext"):
        self.context = context
        self.workers: list[Worker] = []
        self._api_task: asyncio.Task | None = None
        self._config_reloader: ConfigReloader | None = None  # Add this
```

Modify `_setup_workers` method:
```python
    def _setup_workers(self) -> None:
        """Create all workers."""
        self.workers.append(AgentDispatcherWorker(self.context))
        self.workers.append(CronWorker(self.context))

        # Start config hot reload
        self._config_reloader = ConfigReloader(self.context.config)
        self._config_reloader.start()

        if self.context.config.messagebus.enabled:
            buses = self.context.messagebus_buses
            if buses:
                self.workers.append(MessageBusWorker(self.context))
                logger.info(f"MessageBus enabled with {len(buses)} bus(es)")
            else:
                logger.warning("MessageBus enabled but no buses configured")
```

Modify `_stop_all` method:
```python
    async def _stop_all(self) -> None:
        """Stop all workers gracefully."""
        for worker in self.workers:
            await worker.stop()

        # Stop config reloader
        if self._config_reloader is not None:
            self._config_reloader.stop()
```

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/server/test_server.py -v`
Expected: All tests pass

**Step 5: Commit**

```bash
git add src/picklebot/server/server.py tests/server/test_server.py
git commit -m "feat(server): integrate ConfigReloader for hot reload"
```

---

## Task 6: Run full test suite

**Step 1: Run all tests**

Run: `uv run pytest -v`
Expected: All tests pass

**Step 2: Run linting**

Run: `uv run black . && uv run ruff check .`
Expected: No errors

**Step 3: Final commit (if any fixes needed)**

```bash
git add -A
git commit -m "fix: clean up after config hot reload implementation"
```

---

## Summary

After completing all tasks:
1. `watchdog` dependency added
2. `Config.reload()` method re-reads config files
3. `ConfigHandler` responds to file modification events
4. `ConfigReloader` manages the watchdog observer lifecycle
5. Server integrates reloader on startup/shutdown
6. All tests pass
