---
name: skill-creator
description: Search, install, verify, and create skills for pickle-bot
---

Help users add new skills to pickle-bot.

## What is a Skill?

A skill is a reusable prompt that enhances an agent's capabilities. Skills are stored as `SKILL.md` files at `{{skills_path}}/<name>/SKILL.md`.

## Workflow

### 1. Search for Existing Skills

First, search online for existing skills:
```bash
npx skills find <query>           # Search skills.sh registry
npx clawhub search <query>        # Search ClawHub registry
npx clawhub explore               # Browse latest skills
```

If a suitable skill exists, install it:
```bash
npx skills add <package>          # e.g., npx skills add vercel-labs/agent-skills
npx clawhub install <slug>        # Install from ClawHub
```

### 2. Verify Installed Skill

After installation, verify:

**Validity:**
- Valid YAML frontmatter with `name` and `description`
- Proper markdown structure

**Safety:**
- No arbitrary code execution outside tools
- No file operations outside workspace paths
- No credentials or secrets in skill content

### 3. Create New Skill (if needed)

If no existing skill fits, create from scratch:

1. Ask what the skill should do
2. Suggest a name and description
3. Draft the skill content
4. Create at `{{skills_path}}/<name>/SKILL.md`

## Skill Template

```markdown
---
name: skill-name
description: What this skill does
---

Skill instructions and guidance here.
```

## Best Practices

- Skill name in frontmatter should match the folder name
- Keep skills focused on one capability
- Use clear, actionable instructions
- Reference template variables like `{{workspace}}` when paths are needed
