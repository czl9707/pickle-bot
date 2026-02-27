"""Tests for Agent event publishing."""

import time
from unittest.mock import AsyncMock, patch

import pytest

from picklebot.core.agent import Agent, SessionMode
from picklebot.core.agent_loader import AgentDef
from picklebot.core.context import SharedContext
from picklebot.events.types import Event, EventType
from picklebot.utils.config import Config, LLMConfig


@pytest.fixture
def mock_config(tmp_path) -> Config:
    """Config with workspace pointing to tmp_path."""
    return Config(
        workspace=tmp_path,
        llm=LLMConfig(provider="openai", model="gpt-4", api_key="test-key"),
        default_agent="test",
    )


@pytest.fixture
def mock_context(mock_config) -> SharedContext:
    """SharedContext with test config."""
    return SharedContext(config=mock_config)


@pytest.fixture
def mock_agent_def() -> AgentDef:
    """Minimal AgentDef for testing."""
    return AgentDef(
        id="test-agent",
        name="Test Agent",
        description="A test agent",
        system_prompt="You are a test assistant.",
        llm=LLMConfig(provider="openai", model="gpt-4", api_key="test-key"),
    )


@pytest.fixture
def mock_agent(mock_context: SharedContext, mock_agent_def: AgentDef) -> Agent:
    """Agent instance for testing."""
    return Agent(agent_def=mock_agent_def, context=mock_context)


@pytest.mark.asyncio
async def test_chat_publishes_outbound_event(
    mock_agent: Agent, mock_context: SharedContext
):
    """AgentSession.chat should publish an OUTBOUND event."""
    # Create session
    session = mock_agent.new_session(SessionMode.CHAT)

    # Subscribe to OUTBOUND events to capture what's published
    published_events: list[Event] = []

    async def capture_event(event: Event):
        published_events.append(event)

    mock_context.eventbus.subscribe(EventType.OUTBOUND, capture_event)

    # Mock the LLM to return a response
    with patch.object(mock_agent.llm, "chat", new_callable=AsyncMock) as mock_llm_chat:
        mock_llm_chat.return_value = ("Hello! How can I help you?", [])

        # Call chat
        response = await session.chat("Hi")

    # Verify response
    assert response == "Hello! How can I help you?"

    # Verify OUTBOUND event was published
    assert len(published_events) == 1
    event = published_events[0]

    assert event.type == EventType.OUTBOUND
    assert event.session_id == session.session_id
    assert event.content == "Hello! How can I help you?"
    assert event.source == f"agent:{mock_agent.agent_def.id}"
    assert event.timestamp is not None
    assert event.metadata.get("agent_id") == mock_agent.agent_def.id


@pytest.mark.asyncio
async def test_chat_event_has_valid_timestamp(
    mock_agent: Agent, mock_context: SharedContext
):
    """Published OUTBOUND event should have a valid timestamp."""
    session = mock_agent.new_session(SessionMode.CHAT)

    published_events: list[Event] = []

    async def capture_event(event: Event):
        published_events.append(event)

    mock_context.eventbus.subscribe(EventType.OUTBOUND, capture_event)

    before_time = time.time()

    with patch.object(mock_agent.llm, "chat", new_callable=AsyncMock) as mock_llm_chat:
        mock_llm_chat.return_value = ("Response", [])

        await session.chat("Test")

    after_time = time.time()

    assert len(published_events) == 1
    event = published_events[0]

    # Timestamp should be between before and after
    assert before_time <= event.timestamp <= after_time


@pytest.mark.asyncio
async def test_chat_with_tool_calls_publishes_outbound_event(
    mock_agent: Agent, mock_context: SharedContext
):
    """AgentSession.chat should publish OUTBOUND event even after tool calls."""
    from picklebot.provider.llm import LLMToolCall

    session = mock_agent.new_session(SessionMode.CHAT)

    published_events: list[Event] = []

    async def capture_event(event: Event):
        published_events.append(event)

    mock_context.eventbus.subscribe(EventType.OUTBOUND, capture_event)

    # Mock LLM to first return tool call, then final response
    tool_call = LLMToolCall(
        id="call-1", name="read_file", arguments='{"path": "/tmp/test.txt"}'
    )

    call_count = 0

    async def mock_chat_response(messages, tool_schemas):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return ("Let me read that file.", [tool_call])
        else:
            return ("The file contains test data.", [])

    with patch.object(mock_agent.llm, "chat", new_callable=AsyncMock) as mock_llm_chat:
        mock_llm_chat.side_effect = mock_chat_response

        # Mock the tool execution
        with patch.object(
            session.tools, "execute_tool", new_callable=AsyncMock
        ) as mock_execute:
            mock_execute.return_value = "File content: test data"

            response = await session.chat("What's in the file?")

    # Verify final response
    assert response == "The file contains test data."

    # Verify only one OUTBOUND event was published (for the final response)
    assert len(published_events) == 1
    event = published_events[0]

    assert event.type == EventType.OUTBOUND
    assert event.content == "The file contains test data."
    assert event.source == f"agent:{mock_agent.agent_def.id}"


@pytest.mark.asyncio
async def test_chat_returns_content_after_publishing_event(
    mock_agent: Agent, mock_context: SharedContext
):
    """AgentSession.chat should return content after publishing the event."""
    session = mock_agent.new_session(SessionMode.CHAT)

    event_publish_order = []
    chat_returned = False

    async def track_event(event: Event):
        event_publish_order.append(("event", event.content))
        # At this point, chat should not have returned yet
        assert not chat_returned

    mock_context.eventbus.subscribe(EventType.OUTBOUND, track_event)

    with patch.object(mock_agent.llm, "chat", new_callable=AsyncMock) as mock_llm_chat:
        mock_llm_chat.return_value = ("Test response", [])

        response = await session.chat("Hi")
        chat_returned = True

    assert response == "Test response"
    assert len(event_publish_order) == 1
    assert event_publish_order[0] == ("event", "Test response")
