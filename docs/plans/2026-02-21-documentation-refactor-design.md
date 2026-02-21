# Documentation Refactor Design

## Overview

Refactor README.md and CLAUDE.md to reduce bloat by extracting detailed content into feature-based documentation in docs/. This creates a clear separation: README for quick start, CLAUDE.md for AI context, and docs/ for comprehensive references.

## Goals

- **README.md** - Minimal (~50 lines): what it is, quick start, link to docs
- **CLAUDE.md** - Essential patterns (~100 lines): commands, architecture overview, key conventions
- **docs/** - Comprehensive references (~750 lines total): configuration, features, architecture, extending

## Approach: Feature-Based Documentation

Split detailed content into topical documents for easy navigation and natural growth.

## File Structure

```
README.md                      (~50 lines)
CLAUDE.md                      (~100 lines)
docs/
  configuration.md             (~150 lines)
  features.md                  (~250 lines)
  architecture.md              (~200 lines)
  extending.md                 (~150 lines)
```

## Content Distribution

### README.md (Minimal Teaser)

**Purpose:** Get someone running in under 2 minutes.

**Content:**
- One-line description
- Quick start (git clone, uv sync, picklebot chat)
- 3-5 bullet points of key features
- Links to documentation
- Development commands
- License

**Removed from current:**
- Detailed config examples → docs/configuration.md
- Full feature descriptions → docs/features.md
- Architecture diagrams → docs/architecture.md
- Code examples → docs/extending.md
- Project structure → docs/architecture.md

---

### CLAUDE.md (AI Context)

**Purpose:** Essential mental model for Claude Code working in the codebase.

**Content:**
- Commands (uv run picklebot chat, server, pytest, etc.)
- Architecture overview (entry points, core flow, key files)
- Critical patterns (Worker architecture, Definition loading, Message conversion, Tool registration, Config loading)
- Key conventions (Workers, Sessions, Tools, MessageBus, Errors)
- "What goes where" map to detailed docs

**Removed from current:**
- Detailed component descriptions → docs/architecture.md
- Full config examples → docs/configuration.md
- Feature system details → docs/features.md
- Extension examples → docs/extending.md

---

### docs/configuration.md (Configuration Reference)

**Purpose:** Complete configuration guide.

**Content:**
- Directory structure (`~/.pickle-bot/`)
- Config file format (system vs user, deep merge)
- All configuration options with examples:
  - LLM settings (provider, model, api_key, api_base)
  - Paths (agents_path, skills_path, crons_path, memories_path, history_path)
  - MessageBus (enabled, default_platform, telegram, discord)
- Message bus setup:
  - Telegram bot token setup
  - Discord bot token setup
  - Whitelist configuration
  - Default chat ID for proactive messaging

**Source material:**
- Config section from CLAUDE.md
- Config examples from README.md
- MessageBus config from both

---

### docs/features.md (Feature Reference)

**Purpose:** Comprehensive feature documentation.

**Content organized by feature:**

**Agents:**
- Definition format (AGENT.md with YAML frontmatter)
- Multi-agent support
- Subagent dispatch system
- Agent-specific LLM overrides

**Skills:**
- Definition format (SKILL.md)
- On-demand capability loading
- How to create skills
- Enabling skills on agents

**Crons:**
- Definition format (CRON.md)
- Schedule format (cron syntax)
- Server mode requirements
- Sequential execution

**Memory System:**
- Cookie agent overview
- Three organizational axes (topics, projects, daily-notes)
- Memory flows (real-time, scheduled, on-demand)
- Memory file format

**MessageBus:**
- Platform support (Telegram, Discord)
- Shared conversation history
- Platform routing rules
- User whitelist
- Proactive messaging with post_message tool

**Heartbeat:**
- Continuous work pattern
- How to assign tasks
- How heartbeat cron works

**Source material:**
- Definition format sections from README.md
- Memory system from CLAUDE.md
- MessageBus details from both
- Heartbeat from CLAUDE.md

---

### docs/architecture.md (Architecture Reference)

**Purpose:** Detailed technical architecture for developers.

**Content:**

**High-Level Architecture:**
- Component diagram
- Request flow: Agent → Tools → LLM → Tool execution → Response

**Component Descriptions:**
- Agent - Main orchestrator
- AgentDef - Definition model
- AgentLoader - Parses AGENT.md files
- AgentSession - Runtime state + persistence
- SharedContext - Resource container
- SkillLoader - Loads SKILL.md files
- CronLoader - Loads CRON.md files
- MessageBus - Platform abstraction
- HistoryStore - JSON persistence
- LLMProvider - Provider abstraction
- ToolRegistry - Tool registration
- def_loader - Shared parsing utilities

**Server Architecture:**
- Worker-based design
- Job flow: MessageBusWorker/CronWorker → Queue → AgentWorker
- Worker base class pattern
- Health monitoring and auto-restart

**Project Structure:**
- Directory tree with descriptions
- What lives where

**Key Design Decisions:**
- Why workers instead of threads
- Why asyncio.Queue for job routing
- Why YAML frontmatter for definitions

**Source material:**
- Architecture section from CLAUDE.md
- Project structure from README.md
- Server architecture from both
- Component descriptions from both

---

### docs/extending.md (Extension Guide)

**Purpose:** How to extend and customize pickle-bot.

**Content:**

**Adding Custom Tools:**
- Using @tool decorator
- Parameter schema definition
- Async function pattern
- Registration in ToolRegistry

**Adding LLM Providers:**
- Inheriting from LLMProvider
- provider_config_name pattern
- Auto-registration mechanism

**Creating Skills:**
- SKILL.md format
- When to create skills vs tools
- Best practices

**Creating Agents:**
- AGENT.md format
- System prompt guidelines
- LLM configuration overrides

**Creating Cron Jobs:**
- CRON.md format
- Schedule syntax
- Prompt writing tips

**Frontend Customization:**
- Frontend interface
- ConsoleFrontend implementation
- Creating custom frontends

**Source material:**
- "Adding Custom Tools" from README.md
- "Adding LLM Providers" from README.md
- Definition format examples from both
- Patterns section from CLAUDE.md

## Migration Path

1. Create new docs/ files with extracted content
2. Update README.md to minimal version
3. Update CLAUDE.md to essential patterns version
4. Verify all links work
5. Commit changes

## Success Criteria

- README.md < 60 lines
- CLAUDE.md < 120 lines
- All detailed content preserved in docs/
- Each doc has single clear purpose
- Easy to find specific information
- No duplicate content across files

## Future Considerations

- Add docs/troubleshooting.md as issues arise
- Add docs/examples/ directory for complex scenarios
- Consider API documentation generation for tools
