"""Tests for subagent dispatch tool factory."""

import asyncio
import json
import time
from unittest.mock import MagicMock

import pytest

from picklebot.core.context import SharedContext
from picklebot.tools.subagent_tool import create_subagent_dispatch_tool
from picklebot.core.events import EventType, DispatchEvent, DispatchResultEvent


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
    async def test_tool_dispatches_and_receives_result_via_eventbus(self, test_config):
        """Subagent dispatch tool should dispatch via EventBus and receive RESULT."""
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
        dispatched_events: list[DispatchEvent] = []

        async def capture_dispatch(event: DispatchEvent) -> None:
            dispatched_events.append(event)

        context.eventbus.subscribe(EventType.DISPATCH, capture_dispatch)

        # Start EventBus worker to process queued events
        eventbus_task = context.eventbus.start()

        try:
            # Create a task that will publish RESULT after DISPATCH is received
            async def send_result():
                # Wait for DISPATCH event
                while not dispatched_events:
                    await asyncio.sleep(0.01)

                # Get the session_id from dispatch event and publish RESULT
                dispatch_event = dispatched_events[0]
                session_id = dispatch_event.session_id

                result_event = DispatchResultEvent(
                    session_id=session_id,
                    agent_id="target-agent",
                    source="agent:target-agent",
                    content="Task completed successfully",
                    timestamp=time.time(),
                )
                await context.eventbus.publish(result_event)

            asyncio.create_task(send_result())

            # Execute
            mock_session = _make_mock_session()
            result = await tool_func.execute(
                session=mock_session, agent_id="target-agent", task="Do something"
            )

            # Verify DISPATCH event was published
            assert len(dispatched_events) == 1
            event = dispatched_events[0]
            assert isinstance(event, DispatchEvent)
            assert event.type == EventType.DISPATCH
            assert event.agent_id == "target-agent"

            # Verify result from RESULT event
            parsed = json.loads(result)
            assert parsed["result"] == "Task completed successfully"
            assert "session_id" in parsed
        finally:
            eventbus_task.cancel()
            try:
                await eventbus_task
            except asyncio.CancelledError:
                pass

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
        dispatched_events: list[DispatchEvent] = []

        async def capture_dispatch(event: DispatchEvent) -> None:
            dispatched_events.append(event)

        context.eventbus.subscribe(EventType.DISPATCH, capture_dispatch)

        # Start EventBus worker to process queued events
        eventbus_task = context.eventbus.start()

        try:
            # Create a task that will publish RESULT
            async def send_result():
                while not dispatched_events:
                    await asyncio.sleep(0.01)

                dispatch_event = dispatched_events[0]
                session_id = dispatch_event.session_id

                result_event = DispatchResultEvent(
                    session_id=session_id,
                    agent_id="target-agent",
                    source="agent:target-agent",
                    content="Done",
                    timestamp=time.time(),
                )
                await context.eventbus.publish(result_event)

            asyncio.create_task(send_result())

            # Execute with context
            mock_session = _make_mock_session()
            await tool_func.execute(
                session=mock_session,
                agent_id="target-agent",
                task="Review this",
                context="The code is in src/main.py",
            )

            # Verify context was included in DISPATCH event content
            assert len(dispatched_events) == 1
            event = dispatched_events[0]
            assert "Review this" in event.content
            assert "Context:" in event.content
            assert "The code is in src/main.py" in event.content
        finally:
            eventbus_task.cancel()
            try:
                await eventbus_task
            except asyncio.CancelledError:
                pass

    @pytest.mark.anyio
    async def test_tool_raises_for_unknown_agent(self, test_config):
        """Subagent dispatch tool should raise for unknown agent_id."""
        # Create an agent so tool_func is not None
        agent_dir = test_config.agents_path / "some-agent"
        agent_dir.mkdir(parents=True)
        agent_file = agent_dir / "AGENT.md"
        agent_file.write_text(
            """---
name: Some Agent
description: An agent
---
You are an agent.
"""
        )

        context = SharedContext(config=test_config)

        tool_func = create_subagent_dispatch_tool("caller", context)
        assert tool_func is not None

        mock_session = _make_mock_session()
        with pytest.raises(ValueError, match="Agent 'unknown-agent' not found"):
            await tool_func.execute(
                session=mock_session, agent_id="unknown-agent", task="Do something"
            )

    @pytest.mark.anyio
    async def test_tool_raises_on_error_result(self, test_config):
        """Subagent dispatch tool should raise when RESULT contains error."""
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
        dispatched_events: list[DispatchEvent] = []

        async def capture_dispatch(event: DispatchEvent) -> None:
            dispatched_events.append(event)

        context.eventbus.subscribe(EventType.DISPATCH, capture_dispatch)

        # Start EventBus worker to process queued events
        eventbus_task = context.eventbus.start()

        try:
            # Create a task that will publish RESULT with error
            async def send_error():
                while not dispatched_events:
                    await asyncio.sleep(0.01)

                dispatch_event = dispatched_events[0]
                session_id = dispatch_event.session_id

                result_event = DispatchResultEvent(
                    session_id=session_id,
                    agent_id="target-agent",
                    source="agent:target-agent",
                    content="",
                    timestamp=time.time(),
                    error="Something went wrong",
                )
                await context.eventbus.publish(result_event)

            asyncio.create_task(send_error())

            # Execute - should raise
            mock_session = _make_mock_session()
            with pytest.raises(Exception, match="Something went wrong"):
                await tool_func.execute(
                    session=mock_session, agent_id="target-agent", task="Do something"
                )
        finally:
            eventbus_task.cancel()
            try:
                await eventbus_task
            except asyncio.CancelledError:
                pass
