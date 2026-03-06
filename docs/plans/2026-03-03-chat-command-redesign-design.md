# Chat Command Redesign Design

**Date:** 2026-03-03
**Status:** Approved

## Problem Statement

The current chat command has three critical UX issues:

1. **Incorrect coloring**: User and agent prompts lack proper color styling
2. **Swallowed input**: Agent responses overwrite the next "You: " prompt due to async I/O race conditions
3. **Error log interference**: Third-party library warnings (e.g., RequestsDependencyWarning) appear during chat

## Solution Overview

Refactor the chat command to use a synchronous loop with response queue, eliminating the CliBus abstraction and consolidating all CLI I/O logic into ChatLoop.

## Architecture

### Current Flow (Problematic)

```
CliBus.run() [async] → ChannelWorker → EventBus → AgentWorker → DeliveryWorker → CliBus.reply()
```

Issues:
- CliBus runs independent async input loop
- Agent responses arrive async and print immediately
- Async printing can happen during "You: " prompt display, causing overwriting

### New Flow (Synchronous)

```
ChatLoop [sync] → get input → publish InboundEvent → wait for OutboundEvent queue → display responses
```

Benefits:
- Clean sequencing: prompt → input → response → next prompt
- No race conditions between input and output
- Simpler architecture (no CliBus needed)

## Component Design

### Eliminated Components

**CliBus** (`src/picklebot/channels/cli_bus.py`)
- Remove entirely
- No longer needed with synchronous chat loop
- CLI I/O moves to ChatLoop

### Modified Components

**ChatLoop** (`src/picklebot/cli/chat.py`)

New responsibilities:
- Handle all CLI I/O directly with Rich Console
- Subscribe to OutboundEvents via EventBus
- Maintain response queue for agent replies
- Drive synchronous interaction loop
- Suppress Python warnings

Key methods:
- `get_user_input()` - Display cyan "You: " prompt and read input
- `display_agent_response()` - Display green "Agent: " with message content
- `handle_outbound_event()` - Add agent responses to queue
- `run()` - Synchronous chat loop

### Unchanged Components

- CliEventSource - Keep for event routing/source tracking
- EventBus - No changes
- AgentWorker - No changes
- DeliveryWorker - Will be removed from CLI workers list
- ChannelWorker - Will be removed from CLI workers list

## Data Flow

### Synchronous Chat Cycle

1. **Input Phase**
   - ChatLoop displays "You: " in cyan
   - Reads user input synchronously
   - Creates InboundEvent with CliEventSource
   - Publishes to EventBus

2. **Processing Phase**
   - AgentWorker picks up InboundEvent (background)
   - Agent processes and generates response
   - AgentWorker publishes OutboundEvent to EventBus
   - AgentWorker acks InboundEvent

3. **Output Phase**
   - ChatLoop's OutboundEvent handler adds response to queue
   - ChatLoop waits for queue to receive response
   - Displays "Agent: " in green + response content
   - Adds blank line separator
   - ChatLoop acks OutboundEvent

4. **Loop**
   - Returns to step 1

## User Experience

### Color Scheme

- User prompt: `You: ` in **cyan**
- Agent prefix: `Agent: ` in **green**
- Agent message content: default console color
- Separator: blank line between exchanges

### Example Output

```
You: Hello, how are you?

Agent: I'm doing well, thank you for asking! How can I help you today?

You: _
```

### Error Handling

- Suppress Python warnings globally at chat startup
- Display user-friendly error messages in red if agent fails
- Graceful exit on quit/exit/EOF

### Input Handling

- Trim whitespace from input
- Skip empty messages
- Case-insensitive quit command detection (quit, exit, q)
- Handle Ctrl+C and Ctrl+D

## Implementation Details

### Files Modified

1. **`src/picklebot/cli/chat.py`** - Major refactor
   - Remove CliBus and ChannelWorker from workers list
   - Add response queue
   - Subscribe to OutboundEvents
   - Implement synchronous loop with styled I/O
   - Add warning suppression

2. **`src/picklebot/channels/cli_bus.py`** - Delete entirely

3. **`src/picklebot/core/context.py`** - Check if CliBus initialization needs removal

### Warning Suppression

```python
import warnings
warnings.filterwarnings("ignore")
```

Applied at chat startup to suppress third-party library warnings.

### Workers List

Current:
```python
self.workers = [
    self.context.eventbus,
    AgentWorker(self.context),
    DeliveryWorker(self.context),
    ChannelWorker(self.context),
]
```

New:
```python
self.workers = [
    self.context.eventbus,
    AgentWorker(self.context),
]
```

- DeliveryWorker removed (ChatLoop handles output)
- ChannelWorker removed (no buses for CLI)

### Event Acknowledgment

- InboundEvent: Acked by AgentWorker after publishing OutboundEvent
- OutboundEvent: Acked by ChatLoop after displaying response

## Testing Considerations

- Manual testing of chat flow
- Verify no output overwriting
- Check warning suppression works
- Test quit/exit commands
- Test Ctrl+C and Ctrl+D handling
- Verify event acknowledgment
- Test error scenarios (agent failures)

## Migration Path

1. Delete `cli_bus.py`
2. Refactor ChatLoop with new logic
3. Remove CliBus from context initialization (if needed)
4. Test thoroughly
5. Deploy

No backward compatibility concerns - CLI chat is internal tool.
