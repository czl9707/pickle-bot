"""Tests for AgentLoader."""

import pytest

from picklebot.core.agent_loader import AgentLoader
from picklebot.utils.def_loader import DefNotFoundError, InvalidDefError


class TestAgentLoaderParsing:
    def test_parse_simple_agent(self, test_config):
        """Parse agent with name and prompt only."""
        agents_dir = test_config.agents_path
        agents_dir.mkdir()
        agent_dir = agents_dir / "pickle"
        agent_dir.mkdir()
        (agent_dir / "AGENT.md").write_text(
            "---\n" "name: Pickle\n" "---\n" "You are a helpful assistant."
        )

        loader = AgentLoader(test_config)
        agent_def = loader.load("pickle")

        assert agent_def.id == "pickle"
        assert agent_def.name == "Pickle"
        assert agent_def.system_prompt == "You are a helpful assistant."
        assert agent_def.llm.provider == "openai"

    def test_parse_agent_with_llm_overrides(self, test_config):
        """Parse agent with LLM overrides."""
        agents_dir = test_config.agents_path
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

        loader = AgentLoader(test_config)
        agent_def = loader.load("pickle")

        assert agent_def.llm.provider == "openai"
        assert agent_def.llm.model == "gpt-4"
        assert agent_def.behavior.temperature == 0.5
        assert agent_def.behavior.max_tokens == 8192

    def test_parse_agent_with_allow_skills(self, test_config):
        """Test AgentLoader parses allow_skills from frontmatter."""
        agents_dir = test_config.agents_path
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

        loader = AgentLoader(test_config)
        agent_def = loader.load("test-agent")

        assert agent_def.allow_skills is True

    def test_parse_agent_without_allow_skills_defaults_false(self, test_config):
        """Test AgentLoader defaults allow_skills to False."""
        agents_dir = test_config.agents_path
        agents_dir.mkdir()
        agent_dir = agents_dir / "test-agent"
        agent_dir.mkdir()
        (agent_dir / "AGENT.md").write_text(
            "---\n" "name: Test Agent\n" "---\n" "System prompt here.\n"
        )

        loader = AgentLoader(test_config)
        agent_def = loader.load("test-agent")

        assert agent_def.allow_skills is False

    def test_load_agent_without_description_defaults_to_empty_string(self, test_config):
        """AgentDef should default description to empty string if not provided."""
        agents_dir = test_config.agents_path
        agents_dir.mkdir()
        agent_dir = agents_dir / "test-agent"
        agent_dir.mkdir()
        (agent_dir / "AGENT.md").write_text(
            "---\n" "name: Test Agent\n" "---\n" "You are a test assistant.\n"
        )

        loader = AgentLoader(test_config)
        agent_def = loader.load("test-agent")

        assert agent_def.description == ""


class TestAgentLoaderErrors:
    def test_raises_not_found_when_folder_missing(self, test_config):
        """Raise DefNotFoundError when folder doesn't exist."""
        agents_dir = test_config.agents_path
        agents_dir.mkdir()
        loader = AgentLoader(test_config)

        with pytest.raises(DefNotFoundError) as exc:
            loader.load("nonexistent")

        assert exc.value.def_id == "nonexistent"

    def test_raises_not_found_when_file_missing(self, test_config):
        """Raise DefNotFoundError when AGENT.md doesn't exist."""
        agents_dir = test_config.agents_path
        agents_dir.mkdir()
        agent_dir = agents_dir / "pickle"
        agent_dir.mkdir()
        # No AGENT.md created

        loader = AgentLoader(test_config)

        with pytest.raises(DefNotFoundError):
            loader.load("pickle")

    def test_raises_invalid_when_missing_name(self, test_config):
        """Raise InvalidDefError when name field is missing."""
        agents_dir = test_config.agents_path
        agents_dir.mkdir()
        agent_dir = agents_dir / "pickle"
        agent_dir.mkdir()
        (agent_dir / "AGENT.md").write_text(
            "---\n" "temperature: 0.5\n" "---\n" "You are a helpful assistant."
        )

        loader = AgentLoader(test_config)

        with pytest.raises(InvalidDefError) as exc:
            loader.load("pickle")

        assert "name" in exc.value.reason


class TestAgentLoaderDiscover:
    def test_discover_agents_returns_all_agents(self, test_config):
        """discover_agents should return list of all valid AgentDef."""
        agents_dir = test_config.agents_path
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

        loader = AgentLoader(test_config)

        # Execute
        agents = loader.discover_agents()

        # Verify
        assert len(agents) == 2
        agent_ids = {a.id for a in agents}
        assert "agent-one" in agent_ids
        assert "agent-two" in agent_ids


class TestAgentLoaderTemplateSubstitution:
    def test_substitutes_memories_path(self, test_config):
        """AgentLoader substitutes {{memories_path}} in system prompt."""
        agents_dir = test_config.agents_path
        agents_dir.mkdir()
        agent_dir = agents_dir / "test-agent"
        agent_dir.mkdir()
        (agent_dir / "AGENT.md").write_text(
            "---\nname: Test\n---\nMemories at: {{memories_path}}"
        )

        loader = AgentLoader(test_config)
        agent_def = loader.load("test-agent")

        expected = f"Memories at: {test_config.memories_path}"
        assert agent_def.system_prompt == expected

    def test_substitutes_multiple_variables(self, test_config):
        """AgentLoader substitutes multiple template variables."""
        agents_dir = test_config.agents_path
        agents_dir.mkdir()
        agent_dir = agents_dir / "test-agent"
        agent_dir.mkdir()
        (agent_dir / "AGENT.md").write_text(
            "---\nname: Test\n---\nWorkspace: {{workspace}}, Skills: {{skills_path}}"
        )

        loader = AgentLoader(test_config)
        agent_def = loader.load("test-agent")

        expected = (
            f"Workspace: {test_config.workspace}, Skills: {test_config.skills_path}"
        )
        assert agent_def.system_prompt == expected

    def test_no_template_variables_unchanged(self, test_config):
        """Agent without templates loads normally."""
        agents_dir = test_config.agents_path
        agents_dir.mkdir()
        agent_dir = agents_dir / "test-agent"
        agent_dir.mkdir()
        (agent_dir / "AGENT.md").write_text("---\nname: Test\n---\nNo templates here.")

        loader = AgentLoader(test_config)
        agent_def = loader.load("test-agent")

        assert agent_def.system_prompt == "No templates here."
