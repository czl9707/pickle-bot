"""Tests for layered prompt architecture (SOUL.md + AGENT.md + workspace context)."""

from pathlib import Path
import uuid

import pytest

from picklebot.core.agent import Agent, AgentSession
from picklebot.core.context import SharedContext
from picklebot.core.context_guard import ContextGuard
from picklebot.core.prompt_builder import PromptBuilder
from picklebot.core.events import CliEventSource
from picklebot.tools.registry import ToolRegistry
from picklebot.utils.config import Config


# Fixture to provide path to default_workspace
@pytest.fixture
def default_workspace() -> Path:
    """Path to default_workspace directory (relative to this test file)."""
    # Get the project root (2 levels up from this test file)
    test_file = Path(__file__).resolve()
    # tests/core/test_layered_prompts.py -> tests/core -> tests -> project_root
    project_root = test_file.parents[2]
    return project_root / "default_workspace"


@pytest.fixture
def workspace_config(default_workspace: Path) -> Config:
    """Config with default_workspace."""
    return Config.load(default_workspace)


@pytest.fixture
def workspace_context(workspace_config: Config) -> SharedContext:
    """SharedContext with default_workspace config."""
    return SharedContext(workspace_config)


class TestPickleAgentLayeredPrompts:
    """Test that pickle agent loads with SOUL.md."""

    def test_loads_soul_md(self, workspace_context: SharedContext):
        """Pickle agent should have SOUL.md loaded."""
        agent_def = workspace_context.agent_loader.load("pickle")

        assert agent_def.soul_md, "Pickle should have SOUL.md"
        assert "friendly cat assistant" in agent_def.soul_md.lower()

    def test_agent_md_excludes_personality(self, workspace_context: SharedContext):
        """AGENT.md should not contain personality section."""
        agent_def = workspace_context.agent_loader.load("pickle")

        assert "## Personality" not in agent_def.agent_md

    def test_agent_has_required_metadata(self, workspace_context: SharedContext):
        """Pickle agent should have required metadata."""
        agent_def = workspace_context.agent_loader.load("pickle")

        assert agent_def.id == "pickle"
        assert agent_def.name  # Should have a name


class TestCookieAgentLayeredPrompts:
    """Test that cookie agent loads with SOUL.md."""

    def test_loads_soul_md(self, workspace_context: SharedContext):
        """Cookie agent should have SOUL.md loaded."""
        agent_def = workspace_context.agent_loader.load("cookie")

        assert agent_def.soul_md, "Cookie should have SOUL.md"
        assert "memory manager" in agent_def.soul_md.lower()

    def test_agent_md_excludes_personality(self, workspace_context: SharedContext):
        """AGENT.md should not contain personality section."""
        agent_def = workspace_context.agent_loader.load("cookie")

        assert "## Personality" not in agent_def.agent_md

    def test_agent_has_required_metadata(self, workspace_context: SharedContext):
        """Cookie agent should have required metadata."""
        agent_def = workspace_context.agent_loader.load("cookie")

        assert agent_def.id == "cookie"
        assert agent_def.name  # Should have a name


class TestPromptConcatenation:
    """Test that PromptBuilder concatenates AGENT.md + SOUL.md + workspace context."""

    @pytest.fixture
    def mock_session(self, workspace_context: SharedContext):
        """Create a minimal AgentSession for testing prompt building."""
        agent_def = workspace_context.agent_loader.load("pickle")
        agent = Agent(agent_def, workspace_context)
        tools = ToolRegistry()  # Empty tool registry for testing
        guard = ContextGuard(shared_context=workspace_context)

        session = AgentSession(
            session_id=str(uuid.uuid4()),
            shared_context=workspace_context,
            agent=agent,
            tools=tools,
            source=CliEventSource(),
            context_guard=guard,
        )
        return session

    def test_includes_agent_md_content(
        self, workspace_context: SharedContext, mock_session
    ):
        """Prompt should include AGENT.md content."""
        builder = PromptBuilder(workspace_context)
        prompt = builder.build(mock_session)

        assert "You are Pickle, a friendly cat assistant" in prompt

    def test_includes_soul_md_with_personality_section(
        self, workspace_context: SharedContext, mock_session
    ):
        """Prompt should include SOUL.md content with Personality header."""
        builder = PromptBuilder(workspace_context)
        prompt = builder.build(mock_session)

        assert "## Personality" in prompt
        assert "warm and genuinely helpful" in prompt

    def test_includes_bootstrap_md(
        self, workspace_context: SharedContext, mock_session
    ):
        """Prompt should include BOOTSTRAP.md content."""
        builder = PromptBuilder(workspace_context)
        prompt = builder.build(mock_session)

        assert "Workspace Guide" in prompt

    def test_includes_agents_md(self, workspace_context: SharedContext, mock_session):
        """Prompt should include AGENTS.md content."""
        builder = PromptBuilder(workspace_context)
        prompt = builder.build(mock_session)

        assert "Available Agents" in prompt

    def test_prompt_length_reasonable(
        self, workspace_context: SharedContext, mock_session
    ):
        """Prompt should have substantial content from all layers."""
        builder = PromptBuilder(workspace_context)
        prompt = builder.build(mock_session)

        # Should be reasonably long (all layers combined)
        assert len(prompt) > 500, "Prompt seems too short"
