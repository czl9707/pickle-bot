"""Test helpers for picklebot test suite."""

from pathlib import Path


def create_test_agent(
    workspace: Path,
    agent_id: str = "test-agent",
    name: str = "Test Agent",
    description: str = "A test agent",
    agent_md: str = "You are a test assistant.",  # Renamed from system_prompt
    **kwargs,
) -> Path:
    """Create a minimal test agent in workspace.

    Args:
        workspace: Path to workspace directory
        agent_id: Agent identifier (folder name)
        name: Agent display name
        description: Agent description
        agent_md: Agent markdown content (from AGENT.md body)
        **kwargs: Additional frontmatter fields (e.g., max_concurrency)

    Returns:
        Path to the agent directory
    """
    agents_dir = workspace / "agents"
    agents_dir.mkdir(parents=True, exist_ok=True)

    agent_dir = agents_dir / agent_id
    agent_dir.mkdir(parents=True, exist_ok=True)

    # Build frontmatter
    frontmatter_lines = [
        f"name: {name}",
        f"description: {description}",
    ]
    for key, value in kwargs.items():
        if isinstance(value, str):
            frontmatter_lines.append(f"{key}: {value}")
        else:
            frontmatter_lines.append(f"{key}: {value}")

    frontmatter = "\n".join(frontmatter_lines)

    agent_md_file = agent_dir / "AGENT.md"
    agent_md_file.write_text(f"---\n{frontmatter}\n---\n{agent_md}\n")

    return agent_dir


def create_test_skill(
    workspace: Path,
    skill_id: str = "test-skill",
    name: str = "Test Skill",
    description: str = "A test skill",
    content: str = "# Test Skill\n\nThis is a test skill.",
) -> Path:
    """Create a minimal test skill in workspace.

    Args:
        workspace: Path to workspace directory
        skill_id: Skill identifier (folder name)
        name: Skill display name
        description: Skill description
        content: Skill markdown content

    Returns:
        Path to the skill directory
    """
    skills_dir = workspace / "skills"
    skills_dir.mkdir(parents=True, exist_ok=True)

    skill_dir = skills_dir / skill_id
    skill_dir.mkdir(parents=True, exist_ok=True)

    skill_md = skill_dir / "SKILL.md"
    skill_md.write_text(
        f"---\nname: {name}\ndescription: {description}\n---\n{content}\n"
    )

    return skill_dir


def create_test_cron(
    workspace: Path,
    cron_id: str = "test-cron",
    name: str = "Test Cron",
    description: str = "A test cron job",
    agent: str = "pickle",
    schedule: str = "0 * * * *",
    prompt: str = "Check for updates.",
    one_off: bool = False,
) -> Path:
    """Create a minimal test cron in workspace.

    Args:
        workspace: Path to workspace directory
        cron_id: Cron identifier (folder name)
        name: Cron display name
        description: Cron description
        agent: Agent to run
        schedule: Cron schedule expression
        prompt: Cron prompt
        one_off: Whether this is a one-off cron

    Returns:
        Path to the cron directory
    """
    crons_dir = workspace / "crons"
    crons_dir.mkdir(parents=True, exist_ok=True)

    cron_dir = crons_dir / cron_id
    cron_dir.mkdir(parents=True, exist_ok=True)

    cron_md = cron_dir / "CRON.md"
    cron_md.write_text(
        f'---\nname: {name}\ndescription: {description}\nagent: {agent}\nschedule: "{schedule}"\none_off: {one_off}\n---\n{prompt}\n'
    )

    return cron_dir
