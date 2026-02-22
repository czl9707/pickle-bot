# Config System Refactor Design

## Problem

The current config system conflates user preferences with system defaults:
- `config.system.yaml` serves as both defaults and potential runtime state
- `config.user.yaml` is the only writable config
- No way for the application to persist runtime state separately from user preferences

Use case: MessageBus recovery needs to persist `current_session_id` - this should not be user-editable.

## Solution

Separate configuration into two files with a three-layer merge:

```
Pydantic defaults (code) ← config.user.yaml ← config.runtime.yaml
```

| File | Purpose | Who writes |
|------|---------|------------|
| `config.user.yaml` | User preferences | `set_user()` method |
| `config.runtime.yaml` | Runtime state | `set_runtime()` method |

## Changes

### 1. Remove `config.system.yaml`

Default values already exist as Pydantic field defaults in `Config` model. No need for a separate defaults file.

### 2. Add `config.runtime.yaml`

New file for application-managed runtime state. Created on first `set_runtime()` call.

### 3. Update `Config.load()`

Three-layer merge:
1. Start with Pydantic defaults
2. Deep merge `config.user.yaml` (if exists)
3. Deep merge `config.runtime.yaml` (if exists)

### 4. Add `set_user()` and `set_runtime()` methods

```python
class Config(BaseModel):
    # ... existing fields ...

    def set_user(self, key: str, value: Any) -> None:
        """Update a config value in config.user.yaml."""
        # Load, update, write back

    def set_runtime(self, key: str, value: Any) -> None:
        """Update a runtime value in config.runtime.yaml."""
        # Load, update, write back, update in-memory
```

### 5. Runtime fields

Runtime fields (e.g., `current_session_id`) will be added to the `Config` model when needed:
- Optional fields with `None` default
- Populated from `config.runtime.yaml` during load
- Not exposed via API

## Migration

- Delete `config.system.yaml` (or ignore if present)
- `config.user.yaml` continues to work unchanged
- `config.runtime.yaml` created on demand

## Files Changed

- `src/picklebot/utils/config.py` - Core changes
- `src/picklebot/api/routers/config.py` - Update to use `set_user()` (optional refactor)
- `tests/` - Update tests for new loading behavior
