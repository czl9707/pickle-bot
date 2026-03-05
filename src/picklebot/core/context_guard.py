"""Context guard for proactive context window management."""

import uuid
from dataclasses import dataclass
from typing import TYPE_CHECKING, cast

from litellm import token_counter
from litellm.types.completion import (
    ChatCompletionMessageParam as Message,
    ChatCompletionAssistantMessageParam,
)

if TYPE_CHECKING:
    from picklebot.core.agent import AgentSession
    from picklebot.core.context import SharedContext
    from picklebot.core.session_state import SessionState


@dataclass
class ContextGuard:
    """Manages context window size with proactive compaction."""

    shared_context: "SharedContext"
    token_threshold: int = 160000  # 80% of 200k context

    def count_tokens(self, messages: list[Message], model: str) -> int:
        """Count tokens using litellm's token_counter.

        Args:
            messages: List of messages to count
            model: Model name for tokenizer selection

        Returns:
            Token count
        """
        if not messages:
            return 0
        return token_counter(model=model, messages=messages)

    def _serialize_messages_for_summary(self, messages: list[Message]) -> str:
        """Serialize messages to plain text for summarization.

        Args:
            messages: List of messages to serialize

        Returns:
            Plain text representation
        """
        lines = []
        for msg in messages:
            role = msg.get("role", "unknown")
            content = msg.get("content", "")
            # Handle tool calls in assistant messages
            if role == "assistant" and msg.get("tool_calls"):
                tool_names = [
                    tc.get("function", {}).get("name", "unknown")
                    for tc in (cast(ChatCompletionAssistantMessageParam, msg)).get(
                        "tool_calls", []
                    )
                ]
                lines.append(
                    f"ASSISTANT: [used tools: {', '.join(tool_names)}] {content}"
                )
            else:
                lines.append(f"{role.upper()}: {content}")
        return "\n".join(lines)

    def _build_compacted_messages(
        self,
        summary: str,
        original_messages: list[Message],
    ) -> list[Message]:
        """Build new message list with summary + recent messages.

        Args:
            summary: Generated summary text
            original_messages: Original message list

        Returns:
            Compacted message list
        """
        keep_count = max(4, int(len(original_messages) * 0.2))
        compress_count = max(2, int(len(original_messages) * 0.5))
        compress_count = min(compress_count, len(original_messages) - keep_count)

        messages: list[Message] = []
        messages.append(
            {
                "role": "user",
                "content": f"[Previous conversation summary]\n{summary}",
            }
        )
        messages.append(
            {
                "role": "assistant",
                "content": "Understood, I have the context.",
            }
        )
        messages.extend(original_messages[compress_count:])
        return messages

    def _build_full_messages(self, state: "SessionState") -> list[Message]:
        """Build full message list (system prompt + history).

        Args:
            state: SessionState containing messages

        Returns:
            Full message list for LLM
        """
        system_prompt = state.shared_context.prompt_builder.build_for_state(state)
        messages: list[Message] = [{"role": "system", "content": system_prompt}]
        messages.extend(state.get_history())
        return messages

    async def check_and_compact(
        self,
        state: "SessionState",
    ) -> tuple[list[Message], "SessionState | None"]:
        """Check token count, compact and roll session if needed.

        Args:
            state: Current session state

        Returns:
            Tuple of (messages to use, new_state or None)
            - (messages, None) when under threshold
            - (compacted_messages, new_state) when rolling
        """
        # Build full messages (system + history)
        messages = self._build_full_messages(state)

        token_count = self.count_tokens(messages, state.agent.llm.model)

        if token_count < self.token_threshold:
            return messages, None

        # Over threshold - compact and roll
        return await self._compact_and_roll(state, messages)

    async def _compact_and_roll(
        self,
        state: "SessionState",
        messages: list[Message],
    ) -> tuple[list[Message], "SessionState"]:
        """Compact history, roll to new session, return new messages.

        Args:
            state: Current session state
            messages: Current full message list (with system prompt)

        Returns:
            Tuple of (compacted messages, new SessionState)
        """
        # Extract history messages (skip system prompt at index 0)
        history_messages = messages[1:]

        # Generate summary of older messages
        summary = await self._generate_summary_from_state(state, history_messages)

        # Roll to new session
        new_state = self._roll_session(state, summary)

        # Build compacted messages with system prompt
        compacted_history = self._build_compacted_messages(summary, history_messages)
        result_messages: list[Message] = [
            {
                "role": "system",
                "content": state.shared_context.prompt_builder.build_for_state(
                    new_state
                ),
            }
        ]
        result_messages.extend(compacted_history)

        return result_messages, new_state

    def _roll_session(self, state: "SessionState", summary: str) -> "SessionState":
        """Create new SessionState with new session ID.

        Args:
            state: Current session state
            summary: Generated summary (for reference)

        Returns:
            New SessionState with fresh session
        """
        from picklebot.core.session_state import SessionState

        # Generate new session ID
        new_session_id = str(uuid.uuid4())

        # Create new session in HistoryStore
        state.shared_context.history_store.create_session(
            state.agent.agent_def.id,
            new_session_id,
            state.source,
        )

        # Update source -> session mapping
        self.shared_context.config.set_runtime(
            f"sources.{state.source}",
            {"session_id": new_session_id},
        )

        # Create and return new SessionState
        return SessionState(
            session_id=new_session_id,
            agent=state.agent,
            messages=[],
            source=state.source,
            shared_context=state.shared_context,
        )

    async def _generate_summary_from_state(
        self,
        state: "SessionState",
        messages: list[Message],
    ) -> str:
        """Generate summary of older messages using agent's LLM.

        Args:
            state: Current session state
            messages: History message list (without system prompt)

        Returns:
            Generated summary text
        """
        keep_count = max(4, int(len(messages) * 0.2))
        compress_count = max(2, int(len(messages) * 0.5))
        compress_count = min(compress_count, len(messages) - keep_count)

        old_messages = messages[:compress_count]

        # Serialize old messages for summary
        old_text = self._serialize_messages_for_summary(old_messages)

        summary_prompt = f"""Summarize the conversation so far. Keep it factual and concise. Focus on key decisions, facts, and user preferences discovered:

{old_text}"""

        # Use agent's LLM to generate summary
        response, _ = await state.agent.llm.chat(
            [{"role": "user", "content": summary_prompt}],
            [],  # No tools needed
        )
        return response

    # Legacy methods for backward compatibility with AgentSession

    async def check_and_compact_legacy(
        self,
        session: "AgentSession",
        messages: list[Message],
    ) -> list[Message]:
        """Check token count, compact and roll session if needed.

        DEPRECATED: Use check_and_compact with SessionState instead.

        Args:
            session: Current agent session
            messages: Current message list

        Returns:
            Messages to use (either original or compacted)
        """
        token_count = self.count_tokens(messages, session.agent.llm.model)

        if token_count < self.token_threshold:
            return messages

        # Over threshold - compact and roll
        return await self._compact_and_roll_legacy(session, messages)

    async def _compact_and_roll_legacy(
        self,
        session: "AgentSession",
        messages: list[Message],
    ) -> list[Message]:
        """Compact history, roll to new session, return new messages.

        DEPRECATED: For backward compatibility only.

        Args:
            session: Current agent session
            messages: Current message list

        Returns:
            Compacted message list
        """
        # Generate summary of older messages
        summary = await self._generate_summary(session, messages)

        # Roll to new session
        self._roll_session_legacy(session, summary)

        # Return compacted messages
        return self._build_compacted_messages(summary, messages)

    def _roll_session_legacy(self, session: "AgentSession", summary: str) -> str:
        """Create new session, update source mapping, return new ID.

        DEPRECATED: For backward compatibility only.

        Args:
            session: Current agent session
            summary: Generated summary (unused here but available)

        Returns:
            New session ID
        """
        # Create new session
        new_session = session.agent.new_session(session.source)

        # Update source -> session mapping
        self.shared_context.config.set_runtime(
            f"sources.{session.source}",
            {"session_id": new_session.session_id},
        )

        return new_session.session_id

    async def _generate_summary(
        self,
        session: "AgentSession",
        messages: list[Message],
    ) -> str:
        """Generate summary of older messages using agent's LLM.

        DEPRECATED: For backward compatibility only.

        Args:
            session: Current agent session
            messages: Current message list

        Returns:
            Generated summary text
        """
        keep_count = max(4, int(len(messages) * 0.2))
        compress_count = max(2, int(len(messages) * 0.5))
        compress_count = min(compress_count, len(messages) - keep_count)

        old_messages = messages[:compress_count]

        # Serialize old messages for summary
        old_text = self._serialize_messages_for_summary(old_messages)

        summary_prompt = f"""Summarize the conversation so far. Keep it factual and concise. Focus on key decisions, facts, and user preferences discovered:

{old_text}"""

        # Use agent's LLM to generate summary
        response, _ = await session.agent.llm.chat(
            [{"role": "user", "content": summary_prompt}],
            [],  # No tools needed
        )
        return response
