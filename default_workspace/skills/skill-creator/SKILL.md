---
name: Skill Creator
description: Search, install, verify, and create skills for pickle-bot
tools:
  - read
  - write
  - bash
---

Help users add new skills to pickle-bot.

## What is a Skill?

A skill is a reusable prompt that enhances an agent's capabilities. Skills are stored as `SKILL.md` files at `{{skills_path}}/<name>/SKILL.md`.

## Workflow

### 1. Search for Existing Skills

First, search online for existing skills:
```bash
npx skills search <query>
npx clawhub search <query>
```

If a suitable skill exists, install it:
```bash
npx skills install <skill-name>
```

### 2. Verify Installed Skill

After installation, verify:

**Validity:**
- Valid YAML frontmatter with `name` and `description`
- Valid tool names (read, write, edit, bash, websearch, webread)
- Proper markdown structure

**Safety:**
- No arbitrary code execution outside tools
- No file operations outside workspace paths
- No credentials or secrets in skill content

### 3. Create New Skill (if needed)

If no existing skill fits, create from scratch:

1. Ask what the skill should do
2. Suggest a name and description
3. Determine required tools
4. Draft the skill content
5. Create at `{{skills_path}}/<name>/SKILL.md`

## Skill Template

```markdown
---
name: Skill Name
description: What this skill does
tools:
  - read
  - write
---

Skill instructions and guidance here.
```

## Best Practices

- Keep skills focused on one capability
- Use clear, actionable instructions
- Include examples when helpful
- Reference template variables like `{{workspace}}` when paths are needed
