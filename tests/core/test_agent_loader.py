"""Tests for AgentLoader."""

from pathlib import Path
import tempfile

import pytest

from picklebot.utils.config import LLMConfig
from picklebot.core.agent_loader import AgentLoader, AgentNotFoundError, InvalidAgentError


class TestExceptions:
    def test_agent_not_found_error(self):
        """AgentNotFoundError includes agent_id."""
        error = AgentNotFoundError("pickle")
        assert "pickle" in str(error)
        assert error.agent_id == "pickle"

    def test_invalid_agent_error(self):
        """InvalidAgentError includes agent_id and reason."""
        error = InvalidAgentError("pickle", "missing name field")
        assert "pickle" in str(error)
        assert "missing name field" in str(error)
        assert error.agent_id == "pickle"
        assert error.reason == "missing name field"


class TestAgentLoaderParsing:
    @pytest.fixture
    def shared_llm(self):
        return LLMConfig(provider="test", model="test-model", api_key="test-key")

    @pytest.fixture
    def temp_agents_dir(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    def test_parse_simple_agent(self, temp_agents_dir, shared_llm):
        """Parse agent with name and prompt only."""
        agent_dir = temp_agents_dir / "pickle"
        agent_dir.mkdir()
        (agent_dir / "AGENT.md").write_text(
            "---\n"
            "name: Pickle\n"
            "---\n"
            "You are a helpful assistant."
        )

        loader = AgentLoader(temp_agents_dir, shared_llm)
        agent_def = loader.load("pickle")

        assert agent_def.id == "pickle"
        assert agent_def.name == "Pickle"
        assert agent_def.system_prompt == "You are a helpful assistant."
        assert agent_def.llm.provider == "test"

    def test_parse_agent_with_llm_overrides(self, temp_agents_dir, shared_llm):
        """Parse agent with LLM overrides."""
        agent_dir = temp_agents_dir / "pickle"
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

        loader = AgentLoader(temp_agents_dir, shared_llm)
        agent_def = loader.load("pickle")

        assert agent_def.llm.provider == "openai"
        assert agent_def.llm.model == "gpt-4"
        assert agent_def.behavior.temperature == 0.5
        assert agent_def.behavior.max_tokens == 8192

    def test_parse_agent_with_delimiter_in_body(self, temp_agents_dir, shared_llm):
        """Parse agent when body contains --- delimiter."""
        agent_dir = temp_agents_dir / "pickle"
        agent_dir.mkdir()
        (agent_dir / "AGENT.md").write_text(
            "---\n"
            "name: Pickle\n"
            "---\n"
            "Here is a separator:\n"
            "---\n"
            "And more content."
        )

        loader = AgentLoader(temp_agents_dir, shared_llm)
        agent_def = loader.load("pickle")

        assert agent_def.name == "Pickle"
        assert "Here is a separator:" in agent_def.system_prompt
        assert "---" in agent_def.system_prompt
        assert "And more content." in agent_def.system_prompt


class TestAgentLoaderErrors:
    @pytest.fixture
    def shared_llm(self):
        return LLMConfig(provider="test", model="test-model", api_key="test-key")

    @pytest.fixture
    def temp_agents_dir(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    def test_raises_not_found_when_folder_missing(self, temp_agents_dir, shared_llm):
        """Raise AgentNotFoundError when folder doesn't exist."""
        loader = AgentLoader(temp_agents_dir, shared_llm)

        with pytest.raises(AgentNotFoundError) as exc:
            loader.load("nonexistent")

        assert exc.value.agent_id == "nonexistent"

    def test_raises_not_found_when_file_missing(self, temp_agents_dir, shared_llm):
        """Raise AgentNotFoundError when AGENT.md doesn't exist."""
        agent_dir = temp_agents_dir / "pickle"
        agent_dir.mkdir()
        # No AGENT.md created

        loader = AgentLoader(temp_agents_dir, shared_llm)

        with pytest.raises(AgentNotFoundError):
            loader.load("pickle")

    def test_raises_invalid_when_missing_name(self, temp_agents_dir, shared_llm):
        """Raise InvalidAgentError when name field is missing."""
        agent_dir = temp_agents_dir / "pickle"
        agent_dir.mkdir()
        (agent_dir / "AGENT.md").write_text(
            "---\n"
            "temperature: 0.5\n"
            "---\n"
            "You are a helpful assistant."
        )

        loader = AgentLoader(temp_agents_dir, shared_llm)

        with pytest.raises(InvalidAgentError) as exc:
            loader.load("pickle")

        assert "name" in exc.value.reason
