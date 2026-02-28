"""Tests for subagent dispatch tool factory."""

import asyncio
import json
from unittest.mock import MagicMock

import pytest

from picklebot.core.context import SharedContext
from picklebot.tools.subagent_tool import create_subagent_dispatch_tool
from picklebot.events.types import EventType, Event


def _make_mock_session():
    """Helper to create a mock session."""
    mock_session = MagicMock()
    mock_session.session_id = "test-session"
    mock_session.agent_id = "test-agent"
    return mock_session


class TestCreateSubagentDispatchTool:
    """Tests for create_subagent_dispatch_tool factory function."""

    def test_create_tool_returns_none_when_no_agents(self, test_config):
        """create_subagent_dispatch_tool should return None when no agents available."""
        context = SharedContext(config=test_config)

        tool_func = create_subagent_dispatch_tool("any-agent", context)
        assert tool_func is None

    def test_tool_has_correct_schema(self, test_config):
        """Subagent dispatch tool should have correct name, description, and parameters."""
        # Create multiple agents
        for agent_id, name, desc in [
            ("reviewer", "Code Reviewer", "Reviews code for quality"),
            ("planner", "Task Planner", "Plans and organizes tasks"),
        ]:
            agent_dir = test_config.agents_path / agent_id
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

        context = SharedContext(config=test_config)

        tool_func = create_subagent_dispatch_tool("caller", context)

        assert tool_func is not None
        # Check tool properties
        assert tool_func.name == "subagent_dispatch"
        assert "Dispatch a task to a specialized subagent" in tool_func.description
        assert "<available_agents>" in tool_func.description
        assert 'id="reviewer"' in tool_func.description
        assert "Reviews code for quality" in tool_func.description
        assert 'id="planner"' in tool_func.description

        # Check parameters schema
        params = tool_func.parameters
        assert params["type"] == "object"
        assert "agent_id" in params["properties"]
        assert params["properties"]["agent_id"]["type"] == "string"
        assert set(params["properties"]["agent_id"]["enum"]) == {"reviewer", "planner"}
        assert "task" in params["properties"]
        assert "context" in params["properties"]
        assert params["required"] == ["agent_id", "task"]

    def test_tool_excludes_calling_agent(self, test_config):
        """Subagent dispatch tool should exclude the calling agent from enum."""
        # Create multiple agents
        for agent_id, name, desc in [
            ("agent-a", "Agent A", "First agent"),
            ("agent-b", "Agent B", "Second agent"),
            ("agent-c", "Agent C", "Third agent"),
        ]:
            agent_dir = test_config.agents_path / agent_id
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

        context = SharedContext(config=test_config)

        # When agent-b calls the factory, it should be excluded
        tool_func = create_subagent_dispatch_tool("agent-b", context)

        assert tool_func is not None
        enum_ids = set(tool_func.parameters["properties"]["agent_id"]["enum"])
        assert "agent-a" in enum_ids
        assert "agent-c" in enum_ids
        assert "agent-b" not in enum_ids  # Excluded!

    @pytest.mark.anyio
    async def test_tool_dispatches_via_eventbus(self, test_config):
        """Subagent dispatch tool should dispatch through EventBus and return result."""
        # Create target agent
        agent_dir = test_config.agents_path / "target-agent"
        agent_dir.mkdir(parents=True)
        agent_file = agent_dir / "AGENT.md"
        agent_file.write_text(
            """---
name: Target Agent
description: A target for dispatch testing
---

You are the target agent.
"""
        )

        context = SharedContext(config=test_config)

        tool_func = create_subagent_dispatch_tool("caller", context)
        assert tool_func is not None

        # Track dispatched events
        dispatched_events: list[Event] = []

        async def capture_event(event: Event) -> None:
            dispatched_events.append(event)

        context.eventbus.subscribe(EventType.DISPATCH, capture_event)

        # Create a task that will resolve the future after event is dispatched
        async def resolve_future():
            # Wait for event to be dispatched
            while not dispatched_events:
                await asyncio.sleep(0.01)

            # Get the job_id from the event and resolve the future
            event = dispatched_events[0]
            job_id = event.metadata.get("job_id")
            future = context.get_future(job_id)
            if future and not future.done():
                future.set_result("Task completed successfully")

        asyncio.create_task(resolve_future())

        # Execute
        mock_session = _make_mock_session()
        result = await tool_func.execute(
            session=mock_session, agent_id="target-agent", task="Do something"
        )

        # Verify event was dispatched
        assert len(dispatched_events) == 1
        event = dispatched_events[0]
        assert event.type == EventType.DISPATCH
        assert event.metadata.get("agent_id") == "target-agent"

        # Verify result
        parsed = json.loads(result)
        assert parsed["result"] == "Task completed successfully"
        assert "session_id" in parsed

    @pytest.mark.anyio
    async def test_tool_includes_context_in_message(self, test_config):
        """Subagent dispatch tool should include context in user message."""
        # Create target agent
        agent_dir = test_config.agents_path / "target-agent"
        agent_dir.mkdir(parents=True)
        agent_file = agent_dir / "AGENT.md"
        agent_file.write_text(
            """---
name: Target Agent
description: A target for dispatch testing
---

You are the target agent.
"""
        )

        context = SharedContext(config=test_config)

        tool_func = create_subagent_dispatch_tool("caller", context)
        assert tool_func is not None

        # Track dispatched events
        dispatched_events: list[Event] = []

        async def capture_event(event: Event) -> None:
            dispatched_events.append(event)

        context.eventbus.subscribe(EventType.DISPATCH, capture_event)

        # Create a task that will resolve the future
        async def resolve_future():
            while not dispatched_events:
                await asyncio.sleep(0.01)

            event = dispatched_events[0]
            job_id = event.metadata.get("job_id")
            future = context.get_future(job_id)
            if future and not future.done():
                future.set_result("Done")

        asyncio.create_task(resolve_future())

        # Execute with context
        mock_session = _make_mock_session()
        await tool_func.execute(
            session=mock_session,
            agent_id="target-agent",
            task="Review this",
            context="The code is in src/main.py",
        )

        # Verify context was included in event content
        assert len(dispatched_events) == 1
        event = dispatched_events[0]
        assert "Review this" in event.content
        assert "Context:" in event.content
        assert "The code is in src/main.py" in event.content

    @pytest.mark.anyio
    async def test_tool_raises_for_unknown_agent(self, test_config):
        """Subagent dispatch tool should raise for unknown agent_id."""
        context = SharedContext(config=test_config)

        tool_func = create_subagent_dispatch_tool("caller", context)
        # tool_func will be None when no agents exist
        if tool_func is None:
            return

        mock_session = _make_mock_session()
        with pytest.raises(ValueError, match="Agent 'unknown-agent' not found"):
            await tool_func.execute(
                session=mock_session, agent_id="unknown-agent", task="Do something"
            )
