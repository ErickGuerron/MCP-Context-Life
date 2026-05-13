# Delta for cross-session-state

## ADDED Requirements

### Requirement: Durable Session State Persistence

The system SHALL persist session state across MCP server restarts using the file system adapter.

The session store MUST write state atomically to prevent corruption on crash.

#### Scenario: Session state persists across restart

- GIVEN a session with active state exists
- WHEN the MCP server restarts
- THEN session state is restored from persisted storage
- AND operations continue without data loss

#### Scenario: Atomic write prevents corruption

- GIVEN a session state update is in progress
- WHEN a crash occurs mid-write
- THEN the previous valid state is not corrupted
- AND recovery uses the last valid snapshot

### Requirement: Session State Journaling

The system SHALL implement journaling for session state changes, enabling recovery to a known-good state after unexpected termination.

#### Scenario: Crash recovery restores valid state

- GIVEN a session was writing state when a crash occurred
- WHEN the server restarts
- THEN the journal is replayed
- AND state is recovered to the last committed entry

### Requirement: Cross-Session State Toggle

Cross-session persistence MUST be configurable:

- `cross_session_state.enabled: false` — uses in-memory state only

#### Scenario: Disabled cross-session uses memory only

- GIVEN `cross_session_state.enabled` is `false`
- WHEN a session ends and restarts
- THEN no state is persisted
- AND a fresh session begins with empty state

### Requirement: Workspace Fingerprint Persistence

The system SHALL persist workspace fingerprint metadata (base prefix hash, RAG hash) across sessions.

#### Scenario: Workspace fingerprint restored

- GIVEN a previously-seen workspace (verified by fingerprint)
- WHEN the MCP server starts
- THEN cached prefix metadata is restored
- AND cache warm-start behavior is enabled

## Edge Cases

### Requirement: Corrupted State Recovery

The system MUST detect and handle corrupted state files gracefully.

#### Scenario: Corrupted state file detected

- GIVEN a state file is corrupted (invalid JSON or checksum mismatch)
- WHEN recovery is attempted
- THEN the corrupted file is archived or renamed
- AND a fresh state begins
- AND a warning is logged

### Requirement: Large State File Handling

The system SHALL limit persisted state size to prevent disk exhaustion.

#### Scenario: State exceeds size limit

- GIVEN persisted state approaches `max_state_size_bytes` (default 10MB)
- WHEN a new session writes state
- THEN older sessions are evicted
- AND a warning is logged about policy

### Requirement: Concurrent Session Writes

The system MUST handle concurrent writes from multiple session instances safely.

#### Scenario: Concurrent writes handled via locking

- GIVEN two session instances attempt to write simultaneously
- WHEN writes are attempted
- THEN file locking or atomic compare-and-swap prevents corruption
- AND one write succeeds while the other retries