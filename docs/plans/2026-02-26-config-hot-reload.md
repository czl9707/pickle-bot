# Config Hot Reload Design

Reload `config.user.yaml` changes without server restart.

## Architecture

```
config.user.yaml  ──watchdog──►  ConfigHandler
                                      │
                                      ▼
                               Config.reload()
                                      │
                                      ▼
                               Workers pick up on next access
```

## Key Interfaces

```python
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

class ConfigHandler(FileSystemEventHandler):
    """Handles config file modification events."""
    def __init__(self, config: Config):
        self._config = config

    def on_modified(self, event):
        """Reload config when config.user.yaml changes."""
        if event.src_path.endswith("config.user.yaml"):
            self._config.reload()

class ConfigReloader:
    """Manages watchdog observer for config hot reload."""

    def __init__(self, config: Config):
        self._config = config
        self._observer: Observer | None = None

    def start(self) -> None:
        """Start watching config file for changes."""

    def stop(self) -> None:
        """Stop watching."""

class Config:
    # Existing methods...

    def reload(self) -> bool:
        """Re-read config.user.yaml, merge with runtime."""
```

## Data Flow

1. `ConfigReloader` starts a `watchdog.Observer` on `config.user.yaml`
2. When file is modified, `ConfigHandler.on_modified()` is called
3. `Config.reload()` re-parses and merges the config
4. Workers pick up new config on next access (no restart needed)

## Design Choices

- **watchdog library (chosen):** Event-driven, immediate detection, OS-native, no CPU waste
- **Polling:** Simpler but wasteful, up to 2s delay

## Integration Points

- **Location:** Update `utils/config.py`, add `ConfigReloader` and `ConfigHandler` classes
- **Dependency:** Add `watchdog` to `pyproject.toml`
- **Usage:** Start in `server/server.py` alongside workers
- **Config:** Add `config.hot_reload: true` option (default: true in server mode)

## References

- claw0 s06_intelligence.py: `BootstrapLoader` reloads files each turn
