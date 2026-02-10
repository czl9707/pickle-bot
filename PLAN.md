# Pickle-Bot Implementation Plan

## Project Status

**MVP - COMPLETED**

The MVP phase is complete with the following features implemented:
1. ✅ Agent skills support - Modular, pluggable skill system
2. ✅ CLI chat interface - Interactive chat through command line
3. ✅ LLM provider abstraction - Multiple providers supported (Z.ai, OpenAI, Anthropic)

**Deferred to later phases:**
- Memory (SQLite storage, vector embeddings, semantic search)
- Heartbeat (Health monitoring, keep-alive, alerts)
- Cron (Job scheduling, built-in maintenance jobs)
- Self-improvement (Reflection, learning, feedback collection)
- TUI (Textual-based terminal UI)

## Architecture Overview

```
┌─────────────────────────────────────────────┐
│           CLI (Typer)                       │
│  - Global --config option                   │
│  - chat command                             │
│  - status command                           │
│  - skills subcommands (list, info, execute) │
└──────────────────┬──────────────────────────┘
                   │
┌──────────────────▼──────────────────────────┐
│           Agent (core/agent.py)             │
│  - LLM provider abstraction                 │
│  - Conversation management                  │
│  - Skill execution coordination             │
└──────────────────┬──────────────────────────┘
                   │
        ┌──────────┴──────────┐
        │                     │
┌───────▼────────┐    ┌──────▼─────────┐
│   Skills       │    │  LLM Provider  │
│   System       │    │  (Abstract)    │
│                │    │                │
│ - BaseSkill    │    │ - ZaiProvider  │
│ - Registry     │    │ - OpenAIProvider│
│ - Built-in     │    │ - AnthropicProvider│
└────────────────┘    └────────────────┘
```

## Directory Structure

```
pickle-bot/
├── main.py                  # CLI entry point
├── pyproject.toml           # Dependencies
├── README.md                # Documentation
├── PLAN.md                  # This file
├── src/
│   └── picklebot/
│       ├── cli/            # CLI interface
│       │   ├── main.py     # Main CLI with global options
│       │   ├── skills.py   # Skills subcommand group
│       │   └── commands.py # Command handlers
│       ├── core/           # Core agent
│       │   ├── agent.py    # Agent class
│       │   ├── config.py   # Config (pydantic models)
│       │   └── state.py    # Agent state
│       ├── llm/            # LLM provider abstraction
│       │   ├── base.py     # BaseLLMProvider
│       │   ├── factory.py  # Provider factory
│       │   └── providers.py # Concrete providers
│       ├── skills/         # Skills system
│       │   ├── base.py     # BaseSkill interface
│       │   ├── registry.py # Skill registry
│       │   └── builtin_skills.py
│       └── utils/          # Utilities
│           └── logging.py  # Logging setup
└── skills/                  # User-installed skills
```

## Configuration

Configuration is stored in `~/.pickle-bot/`:

```
~/.pickle-bot/
├── config.system.yaml    # System defaults
└── config.user.yaml      # User overrides
```

The configuration system uses:
- YAML format for readability
- Pydantic models for validation
- Deep merge for user overrides over system defaults
- No environment variables (pure YAML-driven)

## CLI Commands

```bash
picklebot [OPTIONS] COMMAND [ARGS]...

Options:
  --config, -c TEXT    Path to config directory

Commands:
  chat      Start interactive chat session
  status    Show agent status
  skills    Manage and interact with skills
```

### Skills Subcommands

```bash
picklebot skills list           # List all skills
picklebot skills info <name>     # Show skill details
picklebot skills execute <name>  # Execute a skill
  --args, -a TEXT              # JSON args
```

## Completed Features

### 1. Configuration System
- ✅ YAML-based configuration in `~/.pickle-bot/`
- ✅ System/User config split with deep merge
- ✅ Pydantic validation
- ✅ No environment variables

### 2. LLM Provider Abstraction
- ✅ BaseLLMProvider abstract class
- ✅ Provider factory with registry
- ✅ ZaiProvider (for Z.ai/GLM models)
- ✅ OpenAIProvider (for GPT models)
- ✅ AnthropicProvider (for Claude models)
- ✅ Easy to add new providers

### 3. Skills System
- ✅ BaseSkill abstract class
- ✅ SkillRegistry with tool schema generation
- ✅ Built-in skills: echo, get_time, get_system_info
- ✅ Function calling support

### 4. CLI Interface
- ✅ Global --config option
- ✅ Skills as proper subcommands
- ✅ Rich terminal output
- ✅ Config-driven logging

## Built-in Skills

| Skill | Description |
|-------|-------------|
| echo | Echo back input text (for testing) |
| get_time | Get current time and date |
| get_system_info | Get system information (platform, python, hostname) |

## Dependencies

```toml
dependencies = [
  "litellm>=1.0.0",     # LLM orchestration
  "typer>=0.12.0",      # CLI framework
  "textual>=0.21.0",    # TUI framework (for future use)
  "pydantic>=2.0.0",    # Validation
  "pyyaml>=6.0",        # Config files
  "rich>=13.0.0",       # Terminal formatting
]
```

## Future Phases

### Phase 2: Memory System
- SQLite storage for conversation history
- Vector embeddings for semantic search
- Memory retrieval and consolidation

### Phase 3: Heartbeat & Monitoring
- Health monitoring
- Keep-alive mechanism
- System metrics collection

### Phase 4: Cron & Scheduling
- Job scheduler with cron syntax
- Built-in maintenance jobs
- Job persistence

### Phase 5: Self-Improvement
- Reflection engine
- Learning algorithms
- Feedback collection

### Phase 6: Terminal UI
- Textual-based TUI
- Multiple screens (chat, skills, memory)
- Custom widgets
