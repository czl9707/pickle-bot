# Documentation Refresh Design

**Date:** 2026-02-24
**Status:** Approved

## Overview

Full refresh of pickle-bot documentation to reflect current codebase state and separate user-facing from developer-facing content.

## Doc Purposes After Refresh

| Doc | Audience | Purpose |
|-----|----------|---------|
| **README.md** | Users | What is it, installation, quick start, features overview |
| **CLAUDE.md** | AI assistants | Essential context for working in codebase (commands, key files, high-level flow) |
| **docs/features.md** | Users | How to use each feature (agents, skills, crons, memory, web tools) |
| **docs/configuration.md** | Users | How to configure (single comprehensive YAML example) |
| **docs/architecture.md** | Developers | Internal structure, function calls, patterns, extending |
| **docs/extending.md** | — | Delete (content merged into other docs) |

## Changes by File

### README.md

**Structure:**
1. Tagline (1-2 sentences)
2. Installation (PyPI + from source)
3. Quick Start (onboarding wizard, basic chat)
4. Features (bullet list)
5. Documentation (links)
6. Development (test/lint)
7. License

**Key additions:**
- PyPI installation: `pip install pickle-bot`
- Mention onboarding wizard
- Add web search/read to features

### CLAUDE.md

**Structure:**
1. Commands
2. Architecture Overview (entry points, core flow, key files)
3. Key Conventions (high-level only)
4. What Goes Where (links)

**Key removals (move to architecture.md):**
- Critical Patterns section
- Definition Loading code examples
- HTTP API code examples
- Message Conversion code examples
- Tool Registration code examples
- Config Loading internals
- Nested LLM Config merge logic

### docs/features.md

**Additions:**
- Web Tools section (websearch, webread tools)

**Removals:**
- Internal loader details
- HTTP API implementation details (keep endpoint list)

### docs/configuration.md

**Restructure:**
- Single comprehensive YAML example showing ALL options
- Clear separation of user-managed vs runtime-managed
- Add websearch and webread configuration

**Removals:**
- `set_user()`/`set_runtime()` methods (move to architecture.md)

### docs/architecture.md

**Additions:**
- Provider Architecture section:
  - LLM Providers (`provider/llm/`)
  - Web Search Providers (`provider/web_search/`)
  - Web Read Providers (`provider/web_read/`)
- Tool System section (factories)
- Patterns moved from CLAUDE.md:
  - Definition Loading
  - Message Conversion
  - Config Loading
  - HTTP API Internals

**Updates:**
- All file paths corrected
- Project Structure tree updated

### docs/extending.md

**Action:** Delete

Content distributed to:
- docs/features.md: How to create agents, skills, crons (user-facing)
- docs/architecture.md: How to add tools, providers (developer-facing)

## File Path Corrections

| Old Path | New Path |
|----------|----------|
| `provider/base.py` | `provider/llm/base.py` |
| `provider/providers.py` | `provider/llm/providers.py` |

## New Components to Document

- **Web Search:** `websearch` tool, `WebSearchProvider`, Brave provider
- **Web Read:** `webread` tool, `WebReadProvider`, Crawl4AI provider
- **Onboarding:** `cli/onboarding/` wizard with steps
- **PyPI:** `pip install pickle-bot`
