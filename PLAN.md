# Pickle-Bot MVP Implementation Plan

## Context

Pickle-bot is a personal AI assistant project. **MVP scope focuses on:**
1. **Agent skills support** - Modular, pluggable skill system
2. **CLI chat interface** - Interactive chat through command line
3. **LiteLLM integration** - LLM orchestration with Z.ai provider

**Deferred to later phases:** Memory, heartbeat, cron, self-improvement, TUI

## Architecture Overview

**MVP Architecture** - Simple, focused design:

```
┌─────────────────────────────────────────────┐
│           CLI (Typer)                       │
│  - chat command (interactive)               │
│  - skill commands (list, info, execute)     │
└──────────────────┬──────────────────────────┘
                   │
┌──────────────────▼──────────────────────────┐
│           Agent (core/agent.py)             │
│  - LiteLLM integration (Z.ai)               │
│  - Conversation management                  │
│  - Skill execution coordination             │
└──────────────────┬──────────────────────────┘
                   │
        ┌──────────┴──────────┐
        │                     │
┌───────▼────────┐    ┌──────▼─────────┐
│   Skills       │    │  LiteLLM       │
│   System       │    │  (Z.ai API)    │
│                │    │                │
│ - BaseSkill    │    │ - Chat API     │
│ - Registry     │    │ - Tools/FC     │
│ - Loader       │    │ - Streaming    │
└────────────────┘    └────────────────┘
```

## Directory Structure (MVP)

```
pickle-bot/
├── main.py                          # CLI entry point (Typer)
├── pyproject.toml                   # Dependencies
├── .env                             # API keys (Z.ai)
├── config/
│   └── default.yaml                 # LLM config, skills config
├── picklebot/
│   ├── __init__.py
│   ├── core/
│   │   ├── __init__.py
│   │   ├── agent.py                 # Main Agent class (LiteLLM wrapper)
│   │   ├── config.py                # Configuration (pydantic)
│   │   └── state.py                 # Simple state tracking
│   ├── skills/
│   │   ├── __init__.py
│   │   ├── base.py                  # BaseSkill abstract class
│   │   ├── registry.py              # Skill registry & loader
│   │   └── builtin_skills.py        # Built-in skills (echo, time, system)
│   ├── cli/
│   │   ├── __init__.py
│   │   ├── main.py                  # CLI commands (Typer)
│   │   └── commands.py              # chat, skill list, skill execute
│   └── utils/
│       ├── __init__.py
│       └── logging.py               # Logging setup
├── skills/                          # User-installed skills
│   └── .gitkeep
└── tests/
    └── test_skills/
```

## Implementation Steps (MVP)

### Step 1: Project Setup & Configuration
**Files:** `pyproject.toml`, `.env`, `config/default.yaml`

1. Update `pyproject.toml` with MVP dependencies:
   - `pydantic>=2.0.0` - Config validation
   - `pyyaml>=6.0` - YAML config loading
   - `python-dotenv>=1.0.0` - Environment variables

2. Create `.env` template for Z.ai API key:
   ```
   LITELLM_API_KEY=z_ai_api_key_here
   LITELLM_MODEL=z_ai_model_name
   ```

3. Create `config/default.yaml`:
   ```yaml
   llm:
     provider: z_ai
     model: ${LITELLM_MODEL}
     api_key: ${LITELLM_API_KEY}
     api_base: https://api.z.ai/v1

   agent:
     name: "pickle-bot"
     system_prompt: "You are pickle-bot, a helpful AI assistant."

   skills:
     directory: ./skills
     auto_load: true
   ```

### Step 2: Core Configuration & State
**Files:** `picklebot/core/config.py`, `picklebot/core/state.py`

1. **`config.py`**: Create `AgentConfig` using pydantic BaseModel
   - Load from YAML file
   - Support environment variable interpolation
   - Validate required fields

2. **`state.py`**: Create simple `AgentState` dataclass
   - Track conversation history (in-memory for MVP)
   - Track active skills
   - No persistence needed yet

### Step 3: Agent Core (LiteLLM Integration)
**File:** `picklebot/core/agent.py`

Create `Agent` class with:
- `__init__(config: AgentConfig)` - Initialize with config
- `chat(message: str, stream: bool = True)` - Send message to LLM, return response
- `get_skills_tool_schema()` - Generate tool schemas for LiteLLM
- `_build_litellm_config()` - Build LiteLLM config from agent config

### Step 4: Skills System
**Files:** `picklebot/skills/base.py`, `picklebot/skills/registry.py`, `picklebot/skills/builtin_skills.py`

1. **`base.py`**: Create `BaseSkill` interface
2. **`registry.py`**: Create `SkillRegistry`
3. **`builtin_skills.py`**: Implement built-in skills (echo, time, system)

### Step 5: CLI Commands
**Files:** `main.py`, `picklebot/cli/main.py`, `picklebot/cli/commands.py`

### Step 6: LiteLLM + Skills Integration
Update agent chat to support function calling

## Dependencies (MVP)

```toml
dependencies = [
  "litellm>=7.5.0",        # LLM orchestration
  "typer>=0.21.1",         # CLI framework
  "pydantic>=2.0.0",       # Validation
  "pyyaml>=6.0",           # Config files
  "python-dotenv>=1.0.0",  # Environment variables
  "rich>=13.0.0",          # Terminal formatting
]
```
