# Workspace Guidelines

This workspace contains agents, skills, and scheduled tasks for the pickle-bot assistant system.

## Structure

- `agents/` - Agent definitions (AGENT.md + optional SOUL.md)
- `skills/` - Reusable skill modules (SKILL.md)
- `crons/` - Scheduled tasks (CRON.md)

## Working with Files

- All definitions use YAML frontmatter + Markdown body format
- Template variables like `{{workspace_path}}` are automatically substituted
- Files are loaded at startup and cached for performance

## Best Practices

- Keep agent prompts focused and clear
- Use skills for reusable capabilities
- Test crons with short intervals first before production schedules
