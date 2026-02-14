# Design: Resolve Config Paths at Load Time

## Problem

Currently, `logging.path` and `history.path` in the config are relative strings that must be joined with `workspace` at each usage site. This leads to duplicated path logic:

```python
# logging.py
config.workspace.joinpath(config.logging.path)

# history.py
config.workspace / config.history.path
```

## Solution

Flatten the nested config structure and resolve paths to absolute during config loading using a Pydantic model validator.

## Changes

### 1. Config Model (`utils/config.py`)

**Remove:**
- `LoggingConfig` class
- `HistoryConfig` class

**Update `Config`:**
```python
class Config(BaseModel):
    workspace: Path
    llm: LLMConfig
    agent: AgentConfig = Field(default_factory=AgentConfig)
    logging_path: Path = Field(default=Path(".logs"))
    history_path: Path = Field(default=Path(".history"))

    @model_validator(mode='after')
    def resolve_paths(self) -> 'Config':
        for field in ('logging_path', 'history_path'):
            path = getattr(self, field)
            if path.is_absolute():
                raise ValueError(f"{field} must be relative, got: {path}")
            setattr(self, field, self.workspace / path)
        return self
```

### 2. YAML Config Format

```yaml
# Old
logging:
  path: .logs
history:
  path: .history

# New
logging_path: .logs
history_path: .history
```

### 3. Usage Sites

**`utils/logging.py`:**
```python
# Before
file_handler = logging.FileHandler(config.workspace.joinpath(config.logging.path))

# After
file_handler = logging.FileHandler(config.logging_path)
```

**`core/history.py`:**
```python
# Before
return HistoryStore(config.workspace / config.history.path)

# After
return HistoryStore(config.history_path)
```

## Error Handling

- Absolute paths in config raise `ValidationError` with clear message
- Example: `"logging_path must be relative, got: /var/log"`

## Tests

1. Update existing tests referencing `config.logging.path` → `config.logging_path`
2. Add test for absolute path rejection
3. Add test for path resolution
