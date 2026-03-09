"""Context guard for proactive context window management."""

from dataclasses import dataclass
from typing import TYPE_CHECKING, cast

from litellm import token_counter
from litellm.types.completion import (
    ChatCompletionMessageParam as Message,
    ChatCompletionAssistantMessageParam,
    ChatCompletionToolMessageParam,
)

from picklebot.core.session_state import SessionState

if TYPE_CHECKING:
    from picklebot.core.context import SharedContext
    from picklebot.core.session_state import SessionState


# Default max size for tool result content before truncation
MAX_TOOL_RESULT_CHARS = 10000


@dataclass
class ContextGuard:
    """Manages context window size with proactive compaction."""

    shared_context: "SharedContext"
    token_threshold: int = 160000  # 80% of 200k context
    max_tool_result_chars: int = MAX_TOOL_RESULT_CHARS

    def estimate_tokens(self, state: "SessionState") -> int:
        """Estimate token count for session state.

        Args:
            state: Session state to estimate

        Returns:
            Estimated token count
        """
        if not state.messages:
            return 0
        return token_counter(
            model=state.agent.agent_def.llm.model, messages=state.build_messages()
        )

    async def check_and_compact(
        self,
        state: "SessionState",
    ) -> "SessionState":
        """Check token count, compact and roll session if needed.

        Applies truncation to large tool results when over threshold,
        then falls back to full compaction if still needed.

        Args:
            state: Current session state

        Returns:
            SessionState to use (same state if under threshold,
            same state with truncated content if truncation was sufficient,
            new rolled state if compaction was needed)
        """
        token_count = self.estimate_tokens(state)

        if token_count < self.token_threshold:
            return state

        state.messages = self._truncate_large_tool_results(state.messages)
        token_count = self.estimate_tokens(state)

        if token_count < self.token_threshold:
            return state

        return await self.compact_and_roll(state)

    def _compress_message_count(self, state: "SessionState") -> int:
        keep_count = max(4, int(len(state.messages) * 0.2))
        compress_count = max(2, int(len(state.messages) * 0.5))
        return min(compress_count, len(state.messages) - keep_count)

    def _truncate_large_tool_results(self, messages: list[Message]) -> list[Message]:
        """Truncate oversized tool results to reduce context size.

        Args:
            messages: List of messages to process

        Returns:
            List of messages with large tool results truncated
        """
        result: list[Message] = []
        for msg in messages:
            if msg.get("role") == "tool":
                content = msg.get("content", "")
                if (
                    isinstance(content, str)
                    and len(content) > self.max_tool_result_chars
                ):
                    original_size = len(content)
                    truncated = content[: self.max_tool_result_chars]
                    truncated_content = (
                        f"{truncated}\n\n"
                        f"[Truncated - original size: {original_size} chars]"
                    )

                    msg = cast(ChatCompletionToolMessageParam, {**msg, "content": truncated_content})

            result.append(msg)
        return result

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
        self.shared_context.routing_table.config_source_session_cache(
            str(state.source), new_session.session_id
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
