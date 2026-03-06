# Workspace Guide

## Paths

- Workspace: `{{workspace}}`
- Skills: `{{skills_path}}`
- Crons: `{{crons_path}}`
- Memories: `{{memories_path}}`
- Agents: `{{agents_path}}`

## Directory Structure

```
{{workspace}}
├── config.user.yaml      # User configuration (created by onboarding)
├── config.runtime.yaml   # Runtime state (optional, auto-managed)
├── agents/               # Agent definitions
│   └── {name}/
│       ├── AGENT.md      # Agent config and instructions
│       └── SOUL.md       # Agent personality
├── skills/               # Reusable skills
│   └── {name}/
│       └── SKILL.md      # Skill definition
├── crons/                # Scheduled tasks
│   └── {name}/
│       └── CRON.md      # Skill definition
└── memories/             # Persistent memory storage
    ├── topics/           # Timeless facts
    ├── projects/         # Project-specific context
    └── daily-notes/      # Day-specific events (YYYY-MM-DD.md)
```

## File Purposes

### Agent Files

- **AGENT.md** - Agent configuration and operational instructions
  - Frontmatter: name, description, llm settings
  - Capabilities: what the agent can do
  - Behavioral guidelines: how to handle mistakes, uncertainty
  - Operational instructions: agent-specific procedures

- **SOUL.md** - Agent personality (concatenated with AGENT.md at runtime)
  - Character traits and tone
  - No workspace or dispatch references

### Configuration Files

- **config.user.yaml** - User preferences, API keys, model selection
- **config.runtime.yaml** - Internal runtime state (auto-managed)

### Capability Files

- **SKILL.md** - Reusable skill definition with instructions and scripts
