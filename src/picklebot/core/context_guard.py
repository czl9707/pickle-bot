"""Context guard for proactive context window management."""

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

    async def check_and_compact(
        self,
        session: "AgentSession",
        messages: list[Message],
    ) -> list[Message]:
        """Check token count, compact and roll session if needed.

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
        return await self._compact_and_roll(session, messages)

    async def _compact_and_roll(
        self,
        session: "AgentSession",
        messages: list[Message],
    ) -> list[Message]:
        """Compact history, roll to new session, return new messages.

        Args:
            session: Current agent session
            messages: Current message list

        Returns:
            Compacted message list
        """
        # Generate summary of older messages
        summary = await self._generate_summary(session, messages)

        # Roll to new session
        self._roll_session(session, summary)

        # Return compacted messages
        return self._build_compacted_messages(summary, messages)

    def _roll_session(self, session: "AgentSession", summary: str) -> str:
        """Create new session, update source mapping, return new ID.

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
