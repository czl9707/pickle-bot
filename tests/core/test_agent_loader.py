"""Tests for AgentLoader."""

import pytest
from pydantic import ValidationError

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
        assert agent_def.agent_md == "You are a helpful assistant."
        assert agent_def.llm.provider == "openai"

    def test_parse_agent_with_llm_overrides(self, test_config):
        """Parse agent with nested LLM config."""
        agents_dir = test_config.agents_path
        agents_dir.mkdir()
        agent_dir = agents_dir / "pickle"
        agent_dir.mkdir()
        (agent_dir / "AGENT.md").write_text(
            "---\n"
            "name: Pickle\n"
            "llm:\n"
            "  provider: openai\n"
            "  model: gpt-4\n"
            "  temperature: 0.5\n"
            "  max_tokens: 8192\n"
            "---\n"
            "You are a helpful assistant."
        )

        loader = AgentLoader(test_config)
        agent_def = loader.load("pickle")

        assert agent_def.llm.provider == "openai"
        assert agent_def.llm.model == "gpt-4"
        assert agent_def.llm.temperature == 0.5
        assert agent_def.llm.max_tokens == 8192

    @pytest.mark.parametrize(
        "frontmatter,expected",
        [
            ("allow_skills: true\n", True),
            ("", False),
        ],
        ids=["explicit_true", "default_false"],
    )
    def test_parse_agent_allow_skills(self, test_config, frontmatter, expected):
        """Test AgentLoader parses allow_skills from frontmatter or defaults to False."""
        agents_dir = test_config.agents_path
        agents_dir.mkdir()
        agent_dir = agents_dir / "test-agent"
        agent_dir.mkdir()
        (agent_dir / "AGENT.md").write_text(
            f"---\nname: Test Agent\n{frontmatter}---\nSystem prompt here.\n"
        )

        loader = AgentLoader(test_config)
        agent_def = loader.load("test-agent")

        assert agent_def.allow_skills is expected

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

    def test_parse_agent_llm_deep_merges_with_global(self, test_config):
        """Agent's llm config should deep merge with global config."""
        agents_dir = test_config.agents_path
        agents_dir.mkdir()
        agent_dir = agents_dir / "pickle"
        agent_dir.mkdir()
        # Only override temperature, should inherit provider/model from global
        (agent_dir / "AGENT.md").write_text(
            "---\n"
            "name: Pickle\n"
            "llm:\n"
            "  temperature: 0.3\n"
            "---\n"
            "You are a helpful assistant."
        )

        loader = AgentLoader(test_config)
        agent_def = loader.load("pickle")

        # Inherited from global config
        assert agent_def.llm.provider == "openai"
        assert agent_def.llm.model == "gpt-4"
        # Overridden by agent
        assert agent_def.llm.temperature == 0.3
        # Default from LLMConfig
        assert agent_def.llm.max_tokens == 2048


class TestAgentLoaderErrors:
    @pytest.mark.parametrize(
        "setup_type",
        ["folder_missing", "file_missing"],
    )
    def test_raises_not_found(self, test_config, setup_type):
        """Raise DefNotFoundError when folder or AGENT.md doesn't exist."""
        agents_dir = test_config.agents_path
        agents_dir.mkdir()

        if setup_type == "file_missing":
            agent_dir = agents_dir / "pickle"
            agent_dir.mkdir()
            # No AGENT.md created

        loader = AgentLoader(test_config)

        with pytest.raises(DefNotFoundError):
            loader.load("pickle" if setup_type == "file_missing" else "nonexistent")

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


class TestAgentDefFields:
    def test_agent_def_has_agent_md_and_soul_md(self):
        """AgentDef should have agent_md and soul_md fields."""
        from picklebot.core.agent_loader import AgentDef
        from picklebot.utils.config import LLMConfig

        agent_def = AgentDef(
            id="test",
            name="Test",
            agent_md="You are a test agent.",
            soul_md="Be friendly.",
            llm=LLMConfig(provider="openai", model="gpt-4", api_key="test"),
        )

        assert agent_def.agent_md == "You are a test agent."
        assert agent_def.soul_md == "Be friendly."

    def test_agent_def_has_max_concurrency_with_default(self):
        """AgentDef has max_concurrency field with default value 1."""
        from picklebot.core.agent_loader import AgentDef
        from picklebot.utils.config import LLMConfig

        llm = LLMConfig(provider="test", model="test", api_key="test")
        agent_def = AgentDef(
            id="test",
            name="Test",
            agent_md="Test prompt",
            llm=llm,
        )

        assert agent_def.max_concurrency == 1

    def test_agent_def_max_concurrency_validation(self):
        """max_concurrency must be >= 1."""
        from picklebot.core.agent_loader import AgentDef
        from picklebot.utils.config import LLMConfig

        llm = LLMConfig(provider="test", model="test", api_key="test")

        # Should fail with 0
        with pytest.raises(ValidationError):
            AgentDef(
                id="test",
                name="Test",
                agent_md="Test prompt",
                llm=llm,
                max_concurrency=0,
            )

        # Should fail with negative
        with pytest.raises(ValidationError):
            AgentDef(
                id="test",
                name="Test",
                agent_md="Test prompt",
                llm=llm,
                max_concurrency=-1,
            )


class TestAgentLoaderMaxConcurrency:
    @pytest.mark.parametrize(
        "frontmatter,expected",
        [
            ("max_concurrency: 5\n", 5),
            ("", 1),
        ],
        ids=["explicit_5", "default_1"],
    )
    def test_load_agent_max_concurrency(self, test_config, frontmatter, expected):
        """AgentLoader parses max_concurrency from frontmatter or defaults to 1."""
        agents_dir = test_config.agents_path
        agents_dir.mkdir()
        agent_dir = agents_dir / "test-agent"
        agent_dir.mkdir()
        (agent_dir / "AGENT.md").write_text(
            f"---\nname: Test Agent\n{frontmatter}---\nYou are a test assistant.\n"
        )

        loader = AgentLoader(test_config)
        agent_def = loader.load("test-agent")

        assert agent_def.max_concurrency == expected


class TestAgentLoaderTemplateSubstitution:
    @pytest.mark.parametrize(
        "prompt,expected_content",
        [
            ("Memories at: {{memories_path}}", "memories_path"),
            ("Workspace: {{workspace}}, Skills: {{skills_path}}", "multiple"),
            ("No templates here.", None),
        ],
        ids=["single_variable", "multiple_variables", "no_variables"],
    )
    def test_template_substitution(self, test_config, prompt, expected_content):
        """AgentLoader substitutes template variables in system prompt."""
        agents_dir = test_config.agents_path
        agents_dir.mkdir()
        agent_dir = agents_dir / "test-agent"
        agent_dir.mkdir()
        (agent_dir / "AGENT.md").write_text(f"---\nname: Test\n---\n{prompt}")

        loader = AgentLoader(test_config)
        agent_def = loader.load("test-agent")

        if expected_content == "memories_path":
            expected = f"Memories at: {test_config.memories_path}"
            assert agent_def.agent_md == expected
        elif expected_content == "multiple":
            expected = (
                f"Workspace: {test_config.workspace}, Skills: {test_config.skills_path}"
            )
            assert agent_def.agent_md == expected
        else:
            assert agent_def.agent_md == "No templates here."
