---
name: context-life-governance
description: >
  Detect and act on governance triggers for Context-Life MCP server sessions.
  Triggers: long-message sequences (>15 msgs), repeated-tool (3+ same tool), intent keywords
  (anxiety, goal-oriented, confusion), conversation drift, conversation length tiers, and
  user intent signals.
  Trigger: when governance.triggers.enabled is true (checked via config).
license: Apache-2.0
metadata:
  author: erickguerron
  version: "1.0"
---

## When to Use

- Context window is approaching token budget limits
- Repeated tool calls suggest possible optimization opportunities
- User intent signals indicate frustration, confusion, or goal-directedness
- Session has exceeded short/medium/long conversation thresholds
- Governance alerts need rate-limiting to prevent flooding

## Project Context

- Project: `mcp-context-life` (Python 3.10+, MCP server)
- Config path: `governance.triggers.enabled`, `governance.triggers.long_message_threshold`,
  `governance.triggers.repeated_tool_threshold`
- Feature flag: `governance_triggers_enabled` (from `mmcp.infrastructure.environment.config`)
- Skill reads session messages via `ContextSlice` and orchestrates via `SessionStore` SQLite ledger.

## Trigger Definitions

### 1. Long Message Sequence

**Config**: `governance.triggers.long_message_threshold` (default: 15)

- GIVEN a user has sent `threshold` consecutive messages without agent response
- WHEN the governance skill evaluates context
- THEN a governance alert is triggered with `trigger: long_message`
- AND the skill recommends context optimization

### 2. Repeated Tool Call

**Config**: `governance.triggers.repeated_tool_threshold` (default: 3)

- GIVEN the same tool is called `threshold` times within a 5-minute window
- WHEN the governance skill evaluates
- THEN it detects the repetition pattern with `trigger: repeated_tool`
- AND recommends caching or batching

### 3. User Intent Detection via Keywords

**Keyword sets** (with false-positive guard: require 2+ matches before flagging):

| Category      | Keywords                                                                      |
| ------------- | ----------------------------------------------------------------------------- |
| Anxiety       | "frustrated", "stuck", "not working", "taking forever", "can't", "won't work" |
| Goal-oriented | "just need", "want to", "trying to", "need to", "have to"                     |
| Confusion     | "what", "why is", "how do", "don't understand", "confused", "unclear"         |

- GIVEN a message contains 2+ keywords from the same or mixed categories
- WHEN the governance skill analyzes the message
- THEN it flags the message with `user_intent: {category}`
- AND may trigger preemptive optimization

### 4. Conversation Length Tiers

| Tier   | Message Count | Governance Priority                                     |
| ------ | ------------- | ------------------------------------------------------- |
| Short  | < 10          | Low — minimal overhead                                  |
| Medium | 10–50         | Standard — normal governance                            |
| Long   | > 50          | Elevated — aggressive context trimming may be suggested |

- GIVEN a conversation exceeds a tier boundary
- WHEN the governance skill runs
- THEN it adjusts governance priority accordingly

### 5. Trigger Rate Limiting

**Rule**: Max 1 alert per minute per session.

- GIVEN multiple trigger conditions are met
- WHEN the governance skill would emit multiple alerts
- THEN only the highest-priority alert is emitted
- AND subsequent triggers are suppressed for 60 seconds
- Implementation: track last alert timestamp per session

## Configuration

```toml
[governance]
triggers_enabled = true

[governance.triggers]
long_message_threshold = 15
repeated_tool_threshold = 3
rate_limit_seconds = 60
```

```python
from mmcp.infrastructure.environment.config import get_config

config = get_config()
if not config.governance_triggers_enabled:
    return  # Extended triggers disabled, only base triggers apply
```

## Skill Triggers

The skill activates when:

- `governance.triggers.enabled: true` in config
- AND any of the following are true:
  - Session message count exceeds `long_message_threshold`
  - Tool repetition count exceeds `repeated_tool_threshold`
  - Keyword matches >= 2 in a single message
  - Conversation tier crosses a boundary

## Governance Priority

Priority escalates in this order:

1. **Low** — short conversation, no elevated signals
2. **Medium** — medium conversation OR single elevated signal
3. **High** — long conversation OR repeated elevated signals

## Commands

```bash
pytest tests/test_governance*.py
ruff check mmcp/
```
