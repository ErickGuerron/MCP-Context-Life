# Delta for context-auto-invocation

## ADDED Requirements

### Requirement: Stack Detection

The system MUST detect the execution environment as either `gentle-ai` (multi-agent) or `solo-agent` at the start of each session.

Detection SHALL use `orchestrator_detector.py` logic:
- IF `GENTLE_AI_ACTIVE=1` (env var) AND `.gga` file exists in `cwd` → `gentle-ai`
- ELSE (including partial matches) → `solo-agent`

The detected stack type SHALL be passed to `autoinvoke_context` as a required parameter by the LLM.

#### Scenario: Multi-agent detection (gentle-ai)

- GIVEN the agent starts with `GENTLE_AI_ACTIVE=1` and `.gga` file exists in workspace
- WHEN the system initializes context-life auto-invocation
- THEN stack type MUST be set to `gentle-ai`
- AND `autoinvoke_context` SHALL be called with `stack_type="gentle-ai"`

#### Scenario: Solo-agent detection (Windsurf, Codex, Claude Code)

- GIVEN the agent starts without `GENTLE_AI_ACTIVE` or `.gga` signals
- WHEN the system initializes context-life auto-invocation
- THEN stack type MUST be set to `solo-agent`
- AND `autoinvoke_context` SHALL be called with `stack_type="solo-agent"`

#### Scenario: Partial signal defaults to solo-agent

- GIVEN the agent starts with `GENTLE_AI_ACTIVE=1` but NO `.gga` file is present
- WHEN the system evaluates the stack
- THEN stack type MUST fall back to `solo-agent`
- AND `autoinvoke_context` SHALL be called with `stack_type="solo-agent"`

#### Scenario: DISABLE_AUTOINVOKE flag set

- GIVEN environment variable `DISABLE_AUTOINVOKE=1` is set
- WHEN the system evaluates auto-invocation eligibility
- THEN auto-invocation tool SHALL NOT execute
- AND normal agent workflow SHALL proceed without context-life interception

### Requirement: Auto-Invoke Tool Contract

The MCP server MUST expose `autoinvoke_context(stack_type: str) -> dict` as an MCP tool.
*(Note: `session_id` is intentionally omitted from the tool signature as it is computed securely server-side.)*

The tool MUST return a `ContextPack` dict containing:
- `context_items`: filtered context from Engram
- `session_state`: current session persistence state
- `recommendations`: wake/sleep or handoff suggestions
- `active_session_id`: the ID computed by the server for LLM awareness

The tool SHALL be callable without explicit agent invocation — the host environment MUST trigger it automatically at prompt start.

#### Scenario: Gentle-ai multi-agent flow

- GIVEN stack_type is `gentle-ai`
- WHEN `autoinvoke_context` is invoked
- THEN the tool SHALL call `intercept_user_request` for context extraction
- AND call `index_knowledge` to update knowledge graph
- AND return a `ContextPack` filtered for the orchestrator

#### Scenario: Solo-agent flow with persistence

- GIVEN stack_type is `solo-agent`
- WHEN `autoinvoke_context` is invoked
- THEN the tool SHALL call `intercept_user_request` for context extraction
- AND persist session state to `~/.config/context-life/sessions/{session_id}/state.json`
- AND return `ContextPack` with locally persisted state

#### Scenario: Missing Engram in solo-agent mode

- GIVEN stack_type is `solo-agent` AND Engram is unavailable
- WHEN `autoinvoke_context` is invoked
- THEN the tool SHALL use filesystem persistence as fallback
- AND continue operation without error
- AND log warning that Engram is unavailable

### Requirement: Session ID Derivation (Server-Side)

The MCP Python server MUST derive the `session_id` deterministically without relying on LLM input:

- IF `ENGRAM_SESSION_ID` environment variable exists, use it directly.
- ELSE IF `.context-session.id` file exists in `cwd` and is < 12 hours old, read its value.
- ELSE compute a new hash from `cwd + current_timestamp`, save it to `.context-session.id`, and use it.

The derived session_id SHALL be consistent across all MCP tool calls within the same workspace session.

#### Scenario: Session ID from environment

- GIVEN `ENGRAM_SESSION_ID` environment variable is set to `abc123`
- WHEN session ID is needed
- THEN the system SHALL use `abc123` as the session_id
- AND no hashing occurs

#### Scenario: Session ID from persistent file

- GIVEN no `ENGRAM_SESSION_ID` is set BUT `.context-session.id` exists and is < 12 hours old
- WHEN session ID is needed
- THEN the system SHALL read the session ID from `.context-session.id`
- AND use it without recomputing

#### Scenario: Session ID computed and persisted

- GIVEN no `ENGRAM_SESSION_ID` is set AND `.context-session.id` is missing or expired (>12 hours)
- WHEN session ID is needed
- THEN the system SHALL compute `session_id = hash(cwd + current_timestamp)`
- AND save it to `.context-session.id`
- AND use this for all persistence operations

#### Scenario: Session ID survives server restart

- GIVEN a session file `.context-session.id` exists with valid session_id
- WHEN the MCP server restarts mid-session
- THEN the system SHALL read the existing session_id from the file
- AND maintain session continuity without "amnesia"

## REMOVED Requirements

None.