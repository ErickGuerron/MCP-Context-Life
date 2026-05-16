# Delta for governance-triggers

## ADDED Requirements

### Requirement: Extended Conversation Pattern Triggers

The governance skill SHALL detect additional conversation patterns beyond the base triggers:

- Long message sequences (configurable threshold, default: 15 consecutive messages)
- Repeated tool calls (same tool invoked 3+ times in a window)
- Conversation drift (context grows beyond `max_context_tokens` threshold)

#### Scenario: Long message sequence detected

- GIVEN a user has sent 15+ consecutive messages without agent response
- WHEN the governance skill evaluates context
- THEN a governance alert is triggered
- AND the skill recommends context optimization

#### Scenario: Repeated tool call detection

- GIVEN the same tool is called 3+ times within a 5-minute window
- WHEN the governance skill evaluates
- THEN it detects the repetition pattern
- AND recommends caching or batching

### Requirement: User Intent Detection via Keywords

The governance skill SHALL detect user intent signals through keyword analysis:

- Anxiety keywords: "frustrated", "stuck", "not working", "taking forever"
- Goal-oriented: "just need", "want to", "trying to"
- Confusion signals: "what", "why is", "how do", "don't understand"

#### Scenario: User anxiety keyword detected

- GIVEN a message contains "this is taking forever"
- WHEN the governance skill analyzes the message
- THEN it flags the message with `user_intent: anxiety`
- AND may trigger preemptive optimization

### Requirement: Conversation Length-Based Triggers

The skill SHALL trigger when conversation length exceeds configured thresholds:

- Short conversation: < 10 messages (low governance overhead)
- Medium conversation: 10–50 messages (standard governance)
- Long conversation: > 50 messages (elevated governance priority)

#### Scenario: Long conversation escalates governance priority

- GIVEN a conversation exceeds 50 messages
- WHEN the governance skill runs
- THEN it increases governance priority
- AND may suggest aggressive context trimming

### Requirement: Triggers Configuration

All extended triggers MUST be feature-flagged and configurable:

- `governance.triggers.enabled: false` — disables extended triggers
- `governance.triggers.long_message_threshold: 15`
- `governance.triggers.repeated_tool_threshold: 3`

#### Scenario: Disabled triggers skip evaluation

- GIVEN `governance.triggers.enabled` is `false`
- WHEN governance skill evaluates context
- THEN extended triggers are not evaluated
- AND only base triggers apply

## Edge Cases

### Requirement: Keyword False Positive Mitigation

The system SHALL require at least 2 keyword matches before flagging `user_intent` to reduce false positives.

#### Scenario: Single keyword does not trigger

- GIVEN a message contains only one anxiety keyword
- WHEN the governance skill evaluates
- THEN it does NOT flag user_intent
- AND normal governance applies

### Requirement: Conversation Drift False Positive Guard

Context growth detection MUST verify that the growth is non-purposeful (e.g., not a deliberate large document upload) before triggering.

#### Scenario: Intentional large upload not flagged

- GIVEN a user uploads a file with 8000 tokens of relevant content
- WHEN the governance skill evaluates
- THEN it recognizes the upload as intentional
- AND does not trigger conversation drift alert

### Requirement: Trigger Rate Limiting

The governance skill SHALL rate-limit trigger emissions to prevent alert flooding.

#### Scenario: Triggers rate-limited to 1 per minute

- GIVEN multiple trigger conditions are met
- WHEN the governance skill would emit multiple alerts
- THEN only one alert is emitted per minute per session
- AND subsequent triggers are queued