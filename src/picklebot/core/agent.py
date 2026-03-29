import uuid
import json
import asyncio
from dataclasses import dataclass, field
from datetime import datetime
from typing import TYPE_CHECKING

from picklebot.core.context_guard import ContextGuard
from picklebot.core.events import EventSource
from picklebot.core.session_state import SessionState
from picklebot.provider.llm import LLMProvider
from picklebot.tools.registry import ToolRegistry
from picklebot.tools.skill_tool import create_skill_tool
from picklebot.tools.subagent_tool import create_subagent_dispatch_tool
from picklebot.tools.post_message_tool import create_post_message_tool
from picklebot.tools.websearch_tool import create_websearch_tool
from picklebot.tools.webread_tool import create_webread_tool

from litellm.types.completion import (
    ChatCompletionMessageParam as Message,
    ChatCompletionMessageToolCallParam,
)

if TYPE_CHECKING:
    from picklebot.core.context import SharedContext
    from picklebot.core.agent_loader import AgentDef
    from picklebot.provider.llm import LLMToolCall


class Agent:
    """
    A configured agent that creates and manages conversation sessions.

    Agent is a factory for sessions and holds the LLM and config
    that sessions use for chatting.
    """

    def __init__(self, agent_def: "AgentDef", context: "SharedContext") -> None:
        self.agent_def = agent_def
        self.context = context
        self.llm = LLMProvider.from_config(agent_def.llm)

    def _build_tools(self, include_post_message: bool) -> ToolRegistry:
        """
        Build a ToolRegistry with tools appropriate for the session.

        Args:
            include_post_message: Whether to include the post_message tool

        Returns:
            ToolRegistry with base tools + optional tools
        """
        registry = ToolRegistry.with_builtins()

        # Register skill tool if allowed
        if self.agent_def.allow_skills:
            skill_tool = create_skill_tool(self.context.skill_loader)
            if skill_tool:
                registry.register(skill_tool)

        # Register subagent dispatch tool if other agents exist
        subagent_tool = create_subagent_dispatch_tool(self.agent_def.id, self.context)
        if subagent_tool:
            registry.register(subagent_tool)

        websearch_tool = create_websearch_tool(self.context)
        if websearch_tool:
            registry.register(websearch_tool)

        webread_tool = create_webread_tool(self.context)
        if webread_tool:
            registry.register(webread_tool)

        # Register post_message tool if requested (for cron/job sources)
        if include_post_message:
            post_tool = create_post_message_tool(self.context)
            if post_tool:
                registry.register(post_tool)

        return registry

    def _get_token_threshold(self) -> int:
        """Get token threshold based on model's context window."""
        # Default to 80% of 200k context
        # TODO: Make this configurable per model
        return 160000

    def new_session(
        self,
        source: "EventSource",
        session_id: str | None = None,
    ) -> "AgentSession":
        """
        Create a new conversation session.

        Args:
            source: Event source (e.g., "telegram:user_123", "cron:daily")
            session_id: Optional session_id to use (for recovery scenarios)

        Returns:
            A new Session instance with source-appropriate tools.
        """
        session_id = session_id or str(uuid.uuid4())

        # Build tools for this session
        include_post_message = source.is_cron
        tools = self._build_tools(include_post_message)

        # Create context guard for this session
        context_guard = ContextGuard(
            shared_context=self.context,
            token_threshold=self._get_token_threshold(),
        )

        # Create SessionState
        state = SessionState(
            session_id=session_id,
            agent=self,
            messages=[],
            source=source,
            shared_context=self.context,
        )

        session = AgentSession(
            agent=self,
            state=state,
            context_guard=context_guard,
            tools=tools,
        )

        self.context.history_store.create_session(self.agent_def.id, session_id, source)
        return session

    def resume_session(self, session_id: str) -> "AgentSession":
        """
        Load an existing conversation session.

        Args:
            session_id: The ID of the session to load.

        Returns:
            A Session instance with self as the agent reference.
        """
        session_query = [
            session
            for session in self.context.history_store.list_sessions()
            if session.id == session_id
        ]
        if not session_query:
            raise ValueError(f"Session not found: {session_id}")

        session_info = session_query[0]

        # Get typed EventSource from stored string
        source = session_info.get_source()
        include_post_message = source.is_cron

        # Get all messages (no max_history limit)
        history_messages = self.context.history_store.get_messages(session_id)

        # Convert HistoryMessage to litellm Message format
        messages: list[Message] = [msg.to_message() for msg in history_messages]

        # Build tools for resumed session
        tools = self._build_tools(include_post_message)

        # Create context guard
        context_guard = ContextGuard(
            shared_context=self.context,
            token_threshold=self._get_token_threshold(),
        )

        # Create SessionState with loaded messages
        state = SessionState(
            session_id=session_info.id,
            agent=self,
            messages=messages,
            source=source,
            shared_context=self.context,
        )

        return AgentSession(
            agent=self,
            state=state,
            context_guard=context_guard,
            tools=tools,
        )


@dataclass
class AgentSession:
    """Chat orchestrator - operates on swappable SessionState."""

    agent: Agent
    state: SessionState
    context_guard: ContextGuard
    tools: ToolRegistry
    started_at: datetime = field(default_factory=datetime.now)

    @property
    def session_id(self) -> str:
        """Delegate to state."""
        return self.state.session_id

    @property
    def source(self) -> "EventSource":
        """Delegate to state."""
        return self.state.source

    @property
    def shared_context(self) -> "SharedContext":
        """Delegate to state."""
        return self.state.shared_context

    async def chat(self, message: str) -> str:
        """
        Send a message to the LLM and get a response.

        Args:
            message: User message

        Returns:
            Assistant's response text
        """
        user_msg: Message = {"role": "user", "content": message}
        self.state.add_message(user_msg)

        tool_schemas = self.tools.get_tool_schemas()

        while True:
            messages = self.state.build_messages()
            self.state = await self.context_guard.check_and_compact(self.state)
            content, tool_calls = await self.agent.llm.chat(messages, tool_schemas)

            tool_call_dicts: list[ChatCompletionMessageToolCallParam] = [
                {
                    "id": tc.id,
                    "type": "function",
                    "function": {"name": tc.name, "arguments": tc.arguments},
                }
                for tc in tool_calls
            ]
            assistant_msg: Message = {
                "role": "assistant",
                "content": content,
            }
            if tool_call_dicts:
                assistant_msg["tool_calls"] = tool_call_dicts

            self.state.add_message(assistant_msg)

            if not tool_calls:
                break

            await self._handle_tool_calls(tool_calls)

            continue

        return content

    async def _handle_tool_calls(
        self,
        tool_calls: list["LLMToolCall"],
    ) -> None:
        """
        Handle tool calls from the LLM response.

        Args:
            tool_calls: List of tool calls from LLM response
        """
        tool_call_results = await asyncio.gather(
            *[self._execute_tool_call(tool_call) for tool_call in tool_calls]
        )

        for tool_call, result in zip(tool_calls, tool_call_results):
            tool_msg: Message = {
                "role": "tool",
                "content": result,
                "tool_call_id": tool_call.id,
            }
            self.state.add_message(tool_msg)

    async def _execute_tool_call(
        self,
        tool_call: "LLMToolCall",
    ) -> str:
        """
        Execute a single tool call.

        Args:
            tool_call: Tool call from LLM response

        Returns:
            Tool execution result
        """
        # Extract key arguments
        try:
            args = json.loads(tool_call.arguments)
        except json.JSONDecodeError:
            args = {}

        try:
            result = await self.tools.execute_tool(tool_call.name, session=self, **args)
        except Exception as e:
            result = f"Error executing tool: {e}"

        return result
