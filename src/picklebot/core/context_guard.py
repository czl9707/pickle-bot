"""Context guard for proactive context window management."""

from dataclasses import dataclass
from typing import TYPE_CHECKING, cast

from litellm import token_counter
from litellm.types.completion import (
    ChatCompletionMessageParam as Message,
    ChatCompletionAssistantMessageParam,
)

from picklebot.core.session_state import SessionState

if TYPE_CHECKING:
    from picklebot.core.context import SharedContext
    from picklebot.core.session_state import SessionState


@dataclass
class ContextGuard:
    """Manages context window size with proactive compaction."""

    shared_context: "SharedContext"
    token_threshold: int = 160000  # 80% of 200k context

    def _count_tokens(self, messages: list[Message], model: str) -> int:
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

    def estimate_tokens(self, state: "SessionState") -> int:
        """Estimate token count for session state.

        Args:
            state: Session state to estimate

        Returns:
            Estimated token count
        """
        return self._count_tokens(state.messages, state.agent.agent_def.llm.model)

    async def check_and_compact(
        self,
        state: "SessionState",
    ) -> "SessionState":
        """Check token count, compact and roll session if needed.

        Args:
            state: Current session state
            force: If True, compact even if under threshold

        Returns:
            SessionState to use (same state if under threshold,
            new rolled state if over threshold)
        """
        messages = state.build_messages()
        token_count = self._count_tokens(messages, state.agent.llm.model)

        if token_count < self.token_threshold:
            return state

        return await self.compact_and_roll(state)

    def _compress_message_count(self, state: "SessionState") -> int:
        keep_count = max(4, int(len(state.messages) * 0.2))
        compress_count = max(2, int(len(state.messages) * 0.5))
        return min(compress_count, len(state.messages) - keep_count)

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

    async def compact_and_roll(
        self,
        state: "SessionState",
    ) -> "SessionState":
        """Compact history, roll to new session, return new messages.

        Args:
            state: Current session state
            messages: Current full message list (with system prompt)

        Returns:
            Tuple of (compacted messages, new SessionState)
        """
        new_session = state.agent.new_session(state.source)
        self.shared_context.config.set_runtime(
            f"sources.{state.source}",
            {"session_id": new_session.session_id},
        )

        compacted_history = await self._build_compacted_messages(state)
        for message in compacted_history:
            new_session.state.add_message(message)

        return new_session.state

    async def _build_compacted_messages(
        self,
        state: "SessionState",
    ) -> list[Message]:
        """Generate summary of older messages using agent's LLM.

        Args:
            state: Current session state
            messages: History message list (without system prompt)

        Returns:
            Compacted message list with summary + recent messages
        """
        compress_count = self._compress_message_count(state)

        old_messages = state.messages[:compress_count]
        old_text = self._serialize_messages_for_summary(old_messages)

        summary_prompt = f"""Summarize the conversation so far. Keep it factual and concise. Focus on key decisions, facts, and user preferences discovered:

{old_text}"""

        response, _ = await state.agent.llm.chat(
            [{"role": "user", "content": summary_prompt}],
            [],  # No tools needed
        )

        messages: list[Message] = []
        messages.append(
            {
                "role": "user",
                "content": f"[Previous conversation summary]\n{response}",
            }
        )
        messages.append(
            {
                "role": "assistant",
                "content": "Understood, I have the context.",
            }
        )
        messages.extend(state.messages[compress_count:])
        return messages
