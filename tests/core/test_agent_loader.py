"""Tests for AgentLoader."""

from pathlib import Path
import tempfile

import pytest

from picklebot.utils.config import LLMConfig
from picklebot.core.agent_loader import AgentLoader
from picklebot.utils.def_loader import DefNotFoundError, InvalidDefError


class TestAgentLoaderParsing:
    @pytest.fixture
    def shared_llm(self):
        return LLMConfig(provider="test", model="test-model", api_key="test-key")

    @pytest.fixture
    def temp_workspace(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    def test_parse_simple_agent(self, temp_workspace, shared_llm):
        """Parse agent with name and prompt only."""
        agents_dir = temp_workspace / "agents"
        agents_dir.mkdir()
        agent_dir = agents_dir / "pickle"
        agent_dir.mkdir()
        (agent_dir / "AGENT.md").write_text(
            "---\n" "name: Pickle\n" "---\n" "You are a helpful assistant."
        )

        loader = AgentLoader(agents_dir, shared_llm, temp_workspace)
        agent_def = loader.load("pickle")

        assert agent_def.id == "pickle"
        assert agent_def.name == "Pickle"
        assert agent_def.system_prompt == "You are a helpful assistant."
        assert agent_def.llm.provider == "test"

    def test_parse_agent_with_llm_overrides(self, temp_workspace, shared_llm):
        """Parse agent with LLM overrides."""
        agents_dir = temp_workspace / "agents"
        agents_dir.mkdir()
        agent_dir = agents_dir / "pickle"
        agent_dir.mkdir()
        (agent_dir / "AGENT.md").write_text(
            "---\n"
            "name: Pickle\n"
            "provider: openai\n"
            "model: gpt-4\n"
            "temperature: 0.5\n"
            "max_tokens: 8192\n"
            "---\n"
            "You are a helpful assistant."
        )

        loader = AgentLoader(agents_dir, shared_llm, temp_workspace)
        agent_def = loader.load("pickle")

        assert agent_def.llm.provider == "openai"
        assert agent_def.llm.model == "gpt-4"
        assert agent_def.behavior.temperature == 0.5
        assert agent_def.behavior.max_tokens == 8192

    def test_parse_agent_with_allow_skills(self, temp_workspace, shared_llm):
        """Test AgentLoader parses allow_skills from frontmatter."""
        agents_dir = temp_workspace / "agents"
        agents_dir.mkdir()
        agent_dir = agents_dir / "test-agent"
        agent_dir.mkdir()
        (agent_dir / "AGENT.md").write_text(
            "---\n"
            "name: Test Agent\n"
            "allow_skills: true\n"
            "---\n"
            "System prompt here.\n"
        )

        loader = AgentLoader(agents_dir, shared_llm, temp_workspace)
        agent_def = loader.load("test-agent")

        assert agent_def.allow_skills is True

    def test_parse_agent_without_allow_skills_defaults_false(
        self, temp_workspace, shared_llm
    ):
        """Test AgentLoader defaults allow_skills to False."""
        agents_dir = temp_workspace / "agents"
        agents_dir.mkdir()
        agent_dir = agents_dir / "test-agent"
        agent_dir.mkdir()
        (agent_dir / "AGENT.md").write_text(
            "---\n" "name: Test Agent\n" "---\n" "System prompt here.\n"
        )

        loader = AgentLoader(agents_dir, shared_llm, temp_workspace)
        agent_def = loader.load("test-agent")

        assert agent_def.allow_skills is False

    def test_load_agent_without_description_defaults_to_empty_string(
        self, temp_workspace, shared_llm
    ):
        """AgentDef should default description to empty string if not provided."""
        agents_dir = temp_workspace / "agents"
        agents_dir.mkdir()
        agent_dir = agents_dir / "test-agent"
        agent_dir.mkdir()
        (agent_dir / "AGENT.md").write_text(
            "---\n" "name: Test Agent\n" "---\n" "You are a test assistant.\n"
        )

        loader = AgentLoader(agents_dir, shared_llm, temp_workspace)
        agent_def = loader.load("test-agent")

        assert agent_def.description == ""


class TestAgentLoaderErrors:
    @pytest.fixture
    def shared_llm(self):
        return LLMConfig(provider="test", model="test-model", api_key="test-key")

    @pytest.fixture
    def temp_workspace(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    def test_raises_not_found_when_folder_missing(self, temp_workspace, shared_llm):
        """Raise DefNotFoundError when folder doesn't exist."""
        agents_dir = temp_workspace / "agents"
        agents_dir.mkdir()
        loader = AgentLoader(agents_dir, shared_llm, temp_workspace)

        with pytest.raises(DefNotFoundError) as exc:
            loader.load("nonexistent")

        assert exc.value.def_id == "nonexistent"

    def test_raises_not_found_when_file_missing(self, temp_workspace, shared_llm):
        """Raise DefNotFoundError when AGENT.md doesn't exist."""
        agents_dir = temp_workspace / "agents"
        agents_dir.mkdir()
        agent_dir = agents_dir / "pickle"
        agent_dir.mkdir()
        # No AGENT.md created

        loader = AgentLoader(agents_dir, shared_llm, temp_workspace)

        with pytest.raises(DefNotFoundError):
            loader.load("pickle")

    def test_raises_invalid_when_missing_name(self, temp_workspace, shared_llm):
        """Raise InvalidDefError when name field is missing."""
        agents_dir = temp_workspace / "agents"
        agents_dir.mkdir()
        agent_dir = agents_dir / "pickle"
        agent_dir.mkdir()
        (agent_dir / "AGENT.md").write_text(
            "---\n" "temperature: 0.5\n" "---\n" "You are a helpful assistant."
        )

        loader = AgentLoader(agents_dir, shared_llm, temp_workspace)

        with pytest.raises(InvalidDefError) as exc:
            loader.load("pickle")

        assert "name" in exc.value.reason


class TestAgentLoaderDiscover:
    @pytest.fixture
    def shared_llm(self):
        return LLMConfig(provider="openai", model="gpt-4", api_key="test-key")

    @pytest.fixture
    def temp_workspace(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    def test_discover_agents_returns_all_agents(self, temp_workspace, shared_llm):
        """discover_agents should return list of all valid AgentDef."""
        agents_dir = temp_workspace / "agents"
        agents_dir.mkdir()

        # Create multiple agents
        for agent_id, name, desc in [
            ("agent-one", "Agent One", "First test agent"),
            ("agent-two", "Agent Two", "Second test agent"),
        ]:
            agent_dir = agents_dir / agent_id
            agent_dir.mkdir(parents=True)
            agent_file = agent_dir / "AGENT.md"
            agent_file.write_text(
                f"""---
name: {name}
description: {desc}
---

You are {name}.
"""
            )

        loader = AgentLoader(agents_dir, shared_llm, temp_workspace)

        # Execute
        agents = loader.discover_agents()

        # Verify
        assert len(agents) == 2
        agent_ids = {a.id for a in agents}
        assert "agent-one" in agent_ids
        assert "agent-two" in agent_ids


class TestAgentLoaderTemplateSubstitution:
    @pytest.fixture
    def shared_llm(self):
        return LLMConfig(provider="test", model="test-model", api_key="test-key")

    @pytest.fixture
    def temp_workspace(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    def test_substitutes_memories_path(self, temp_workspace, shared_llm):
        """AgentLoader substitutes {{memories_path}} in system prompt."""
        agents_dir = temp_workspace / "agents"
        agents_dir.mkdir()
        agent_dir = agents_dir / "test-agent"
        agent_dir.mkdir()
        (agent_dir / "AGENT.md").write_text(
            "---\nname: Test\n---\nMemories at: {{memories_path}}"
        )

        loader = AgentLoader(agents_dir, shared_llm, temp_workspace)
        agent_def = loader.load("test-agent")

        expected = f"Memories at: {temp_workspace / 'memories'}"
        assert agent_def.system_prompt == expected

    def test_substitutes_multiple_variables(self, temp_workspace, shared_llm):
        """AgentLoader substitutes multiple template variables."""
        agents_dir = temp_workspace / "agents"
        agents_dir.mkdir()
        agent_dir = agents_dir / "test-agent"
        agent_dir.mkdir()
        (agent_dir / "AGENT.md").write_text(
            "---\nname: Test\n---\nWorkspace: {{workspace}}, Skills: {{skills_path}}"
        )

        loader = AgentLoader(agents_dir, shared_llm, temp_workspace)
        agent_def = loader.load("test-agent")

        expected = f"Workspace: {temp_workspace}, Skills: {temp_workspace / 'skills'}"
        assert agent_def.system_prompt == expected

    def test_no_template_variables_unchanged(self, temp_workspace, shared_llm):
        """Agent without templates loads normally."""
        agents_dir = temp_workspace / "agents"
        agents_dir.mkdir()
        agent_dir = agents_dir / "test-agent"
        agent_dir.mkdir()
        (agent_dir / "AGENT.md").write_text(
            "---\nname: Test\n---\nNo templates here."
        )

        loader = AgentLoader(agents_dir, shared_llm, temp_workspace)
        agent_def = loader.load("test-agent")

        assert agent_def.system_prompt == "No templates here."
