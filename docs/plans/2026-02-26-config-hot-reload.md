# Config Hot Reload Design

Reload `config.user.yaml` changes without server restart.

## Architecture

```
config.user.yaml  ←watcher─→  ConfigReloader
                                   │
                                   ▼
                            Config.reload()
                                   │
                                   ▼
                            SharedContext refresh
```

## Key Interfaces

```python
class ConfigReloader:
    def __init__(self, config: Config, on_change: Callable[[], None] | None = None):
        self._config = config
        self._on_change = on_change
        self._last_mtime: float = 0
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        """Begin polling for config file changes."""

    def stop(self) -> None:
        """Stop watching."""

    def _check_reload(self) -> bool:
        """Check mtime, reload if changed. Returns True if reloaded."""

class Config:
    # Existing methods...

    def reload(self) -> bool:
        """Re-read config.user.yaml, merge with runtime."""
```

## Data Flow

1. `ConfigReloader` polls `config.user.yaml` mtime every 2 seconds
2. On modification detected, call `Config.reload()` to re-parse and merge
3. Optional callback signals `SharedContext` or workers to refresh
4. Workers pick up new config on next access (no restart needed)

## Design Choices

- **Polling (recommended):** Simple, cross-platform, check mtime every 2s
- **watchdog library:** OS-level file events, more complex dependency

## Integration Points

- **Location:** Update `utils/config.py`, add `ConfigReloader` class
- **Usage:** Start in `server/server.py` alongside workers
- **Config:** Add `config.hot_reload: true` option

## References

- claw0 s06_intelligence.py: `BootstrapLoader` reloads files each turn
