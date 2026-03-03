"""Context guard for proactive context window management."""

from dataclasses import dataclass
from typing import TYPE_CHECKING

from litellm import token_counter
from litellm.types.completion import ChatCompletionMessageParam as Message

if TYPE_CHECKING:
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
                    for tc in msg["tool_calls"]
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

        return [
            {
                "role": "user",
                "content": f"[Previous conversation summary]\n{summary}",
            },
            {
                "role": "assistant",
                "content": "Understood, I have the context.",
            },
        ] + original_messages[compress_count:]
