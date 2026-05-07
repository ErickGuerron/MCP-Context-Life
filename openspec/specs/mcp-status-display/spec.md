# mcp-status-display

## Purpose

Display MCP optimization results to the user via tool responses when an orchestrator is detected (advisor mode).

## ADDED Requirements

### Requirement: Status Message Inclusion

When a tool performs prompt optimization (`optimize_messages`, `cache_context`, `intercept_user_request`) and `get_orchestrator_info().advisor_mode` is `True`, the tool response MUST include a visible status message.

The system SHALL append an `optimization_status` field to the tool's JSON result containing:
- The resulting prompt or messages (truncated if exceeds display threshold)
- Original token count and optimized token count
- Number of messages modified
- Optimization strategy applied

#### Scenario: Optimizer modifies prompt

- GIVEN `advisor_mode` is active
- WHEN the optimizer reduces a 8000-token prompt to 3500 tokens
- THEN the tool response includes `optimization_status` with the optimized prompt
- AND shows `8000 → 3500 tokens`
- AND indicates which strategy was used

#### Scenario: No optimization needed

- GIVEN `advisor_mode` is active
- WHEN the optimizer runs but no changes are made
- THEN the tool response MAY omit `optimization_status`
- OR MAY show `0 tokens saved`

### Requirement: Orchestrator Detection

The system SHALL use `get_orchestrator_info().advisor_mode` to determine whether to include status messages.

The detection mechanism MUST NOT modify the MCP protocol or alter existing tool response schemas in a breaking way.

#### Scenario: Advisor mode inactive

- GIVEN `advisor_mode` is `False` or not set
- WHEN a tool performs optimization
- THEN the tool response behaves as before
- AND no `optimization_status` field is added

#### Scenario: Advisor mode active

- GIVEN `advisor_mode` is `True`
- WHEN any optimization-capable tool runs
- THEN status messages are included in the response
- AND the user sees the optimization result

### Requirement: Status Message Format

The `optimization_status` field, when present, MUST be valid JSON with the following shape:
```json
{
  "strategy": "string",
  "original_tokens": "number",
  "optimized_tokens": "number",
  "messages_modified": "number",
  "resulting_prompt": "string (truncated if > 2048 chars)"
}
```

#### Scenario: Valid status message structure

- GIVEN `advisor_mode` is active
- WHEN optimization completes
- THEN the `optimization_status` object contains all required fields
- AND each field has the correct type

#### Scenario: Large prompt truncation

- GIVEN optimization produces a 10000-character prompt
- WHEN the status message is built
- THEN `resulting_prompt` is truncated to 2048 characters
- AND `truncated: true` is added to the status object