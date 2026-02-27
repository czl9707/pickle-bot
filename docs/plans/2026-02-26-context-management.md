# Context Management Design

Protect the agent from context window overflow with a 3-stage retry mechanism.

## Architecture

```
Agent.chat()
    → ContextGuard.guard_api_call()
        → [Attempt 1] Normal call
        → [Attempt 2] Truncate tool_result blocks to 30% budget
        → [Attempt 3] Compact first 50% of messages into LLM summary
        → [Fail] Raise ContextOverflowError
```

## Key Interfaces

```python
class ContextGuard:
    max_tokens: int = 180_000

    def estimate_tokens(self, text: str) -> int:
        """Rough estimate: 1 token per 4 characters."""

    def truncate_tool_result(self, result: str, max_fraction: float = 0.3) -> str:
        """Head-only truncation: keep first max_fraction of context budget."""

    def compact_history(self, messages: list, client: LLMClient, model: str) -> list:
        """Compress first 50% of messages into an LLM-generated summary."""

    def guard_api_call(self, client, model, system, messages, tools, max_retries: int = 2) -> Response:
        """3-stage retry: normal → truncate → compact → raise."""
```

## Data Flow

1. Before LLM call, estimate total token count
2. On context overflow exception:
   - **Stage 1:** Truncate oversized `tool_result` blocks to 30% of budget
   - **Stage 2:** Compact old messages via LLM summary (keep last 20% as-is)
   - **Stage 3:** Raise `ContextOverflowError` if still failing
3. Replace compacted portion with `[Previous conversation summary]` block

## Integration Points

- **Location:** New module `core/context_guard.py`
- **Usage:** Wrap LLM calls in `provider/llm/base.py` or `core/agent.py`
- **Config:** Add `context.max_tokens` to `config.user.yaml`

## References

- claw0 s03_sessions.py: `ContextGuard` class
