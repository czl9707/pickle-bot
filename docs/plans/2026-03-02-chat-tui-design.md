# Chat TUI Design

## Problem

The current `picklebot chat` command uses simple `input()` and `print()` which:
- Doesn't support scrolling through message history
- Input blocks the terminal, no persistent input at bottom
- Poor user experience for longer conversations

## Solution

Replace the simple CLI with a Textual-based TUI that provides:
- Scrollable message history area
- Fixed input field at the bottom (always visible)
- Markdown rendering for agent messages
- Distinct styling for user/agent/error messages

## Design

### Architecture

**Components:**
1. **ChatApp** (Textual App) - Main TUI application
2. **MessageHistory** (Widget) - Scrollable conversation display
3. **InputBar** (Widget) - Fixed single-line input at bottom
4. **CliBus** (Channel) - Connects Textual to event system

**Event Flow:**
```
User types → InputBar → CliBus → InboundEvent → [existing workers]
OutboundEvent → CliBus → MessageHistory display
```

### File Structure

```
src/picklebot/
├── cli/
│   ├── chat.py              # Updated to use ChatApp
│   ├── cli_bus.py           # MOVED from channels/, rewritten with Textual
│   └── tui/                 # NEW: TUI components
│       ├── __init__.py
│       ├── app.py           # ChatApp
│       ├── widgets.py       # MessageHistory, InputBar
│       └── styles.css       # Textual CSS
└── channels/
    ├── base.py              # Channel base class
    ├── telegram_bus.py      # Platform buses
    └── discord_bus.py
```

### CliBus Implementation

**Location:** `cli/cli_bus.py` (moved from `channels/`)

**Responsibilities:**
- Implements `Channel[CliEventSource]` interface
- Launches Textual ChatApp in `run()` method
- Receives messages from ChatApp and calls `on_message` callback (emits InboundEvent)
- Implements `reply()` to display OutboundEvents in ChatApp

**Key Methods:**
```python
async def run(self, on_message: Callable[[str, CliEventSource], Awaitable[None]]) -> None:
    # Launch Textual app with callback
    self.app = ChatApp(on_message=on_message)
    await self.app.run_async()

async def reply(self, content: str, source: CliEventSource) -> None:
    # Post message to Textual app for display
    self.app.post_message(AgentMessage(content=content))
```

### ChatApp (Textual App)

**Location:** `cli/tui/app.py`

**Layout:**
```
┌─────────────────────────────────────────┐
│ MessageHistory (scrollable)             │
│                                         │
│ User: What's the weather?               │
│                                         │
│ Agent: The weather today is sunny...    │
│                                         │
│ Error: API timeout occurred             │
│                                         │
└─────────────────────────────────────────┘
┌─────────────────────────────────────────┐
│ > [input cursor here]                   │
└─────────────────────────────────────────┘
```

**Behavior:**
- Composes MessageHistory + InputBar widgets
- Handles Ctrl+C to quit
- Auto-scrolls to bottom on new messages

### MessageHistory Widget

**Location:** `cli/tui/widgets.py`

**Features:**
- ScrollableContainer with message items
- Renders markdown in agent messages (using Rich)
- Auto-scrolls to bottom when new message added
- Supports mouse scrolling and Page Up/Down

**Message Types:**
1. **UserMessage** - Cyan/blue styling, "User: " prefix
2. **AgentMessage** - Green styling, markdown rendered
3. **ErrorMessage** - Red styling, "Error: " prefix

### InputBar Widget

**Location:** `cli/tui/widgets.py`

**Features:**
- Single-line Input widget
- Fixed at bottom of screen
- Enter sends message
- Empty messages ignored

### Styling

**Location:** `cli/tui/styles.css`

```css
MessageHistory {
    height: 1fr;
    background: $surface;
}

InputBar {
    height: auto;
    background: $panel;
    padding: 1;
}

UserMessage {
    color: cyan;
}

AgentMessage {
    color: green;
}

ErrorMessage {
    color: red;
}
```

### Event Integration

**OutboundEvent Handling:**
The `CliBus.reply()` checks `OutboundEvent.error` field:
- If `error` is set: Display as ErrorMessage
- Otherwise: Display as AgentMessage with markdown rendering

**InboundEvent Flow:**
1. User types in InputBar and presses Enter
2. InputBar calls `on_message` callback
3. CliBus creates InboundEvent and emits to EventBus
4. Existing workers (AgentWorker, etc.) process normally

### Migration Plan

**Step 1: Create TUI components**
- Create `cli/tui/` directory structure
- Implement `app.py`, `widgets.py`, `styles.css`
- Keep existing `channels/cli_bus.py` unchanged

**Step 2: Move and rewrite CliBus**
- Move `channels/cli_bus.py` → `cli/cli_bus.py`
- Rewrite to use Textual components
- Update imports in `cli/chat.py`

**Step 3: Update imports**
- Update `cli/chat.py` to import from `cli.cli_bus`
- Update any test files importing from old location
- Remove old `channels/cli_bus.py`

**Step 4: Add dependencies**
- Add `textual` to project dependencies (pyproject.toml)

## Testing

### Test Files

```
tests/
├── cli/
│   ├── test_chat.py           # Integration test
│   └── test_cli_bus.py        # Unit tests for new CliBus
```

### Test Scenarios

1. **User input creates InboundEvent**
   - Type message, press Enter
   - Verify InboundEvent emitted with correct source

2. **OutboundEvent displays correctly**
   - Emit OutboundEvent with content
   - Verify appears in message history with agent styling

3. **Error message displays correctly**
   - Emit OutboundEvent with error field set
   - Verify appears with error styling

4. **Empty input ignored**
   - Submit empty message
   - Verify no InboundEvent emitted

5. **Ctrl+C exits cleanly**
   - Press Ctrl+C
   - Verify app closes without error

6. **Scrolling works**
   - Add many messages
   - Verify can scroll up and auto-scrolls on new message

## Dependencies

**New dependency:**
- `textual>=0.47.0` (or latest stable version)

**Existing dependencies (already in use):**
- `rich` (Textual is built on Rich)

## Files Changed

| File | Change |
|------|--------|
| `channels/cli_bus.py` | DELETE (moved to cli/) |
| `cli/cli_bus.py` | NEW (moved from channels/, rewritten with Textual) |
| `cli/chat.py` | Update to use new CliBus location |
| `cli/tui/__init__.py` | NEW |
| `cli/tui/app.py` | NEW - ChatApp |
| `cli/tui/widgets.py` | NEW - MessageHistory, InputBar |
| `cli/tui/styles.css` | NEW - Textual styling |
| `pyproject.toml` | Add textual dependency |
| `tests/channels/test_cli_bus.py` | DELETE (moved to cli/) |
| `tests/cli/test_cli_bus.py` | NEW - Unit tests for CliBus |
