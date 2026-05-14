# Delta for context-slice-enriched

## Purpose

Extend ContextSlice to carry technical metadata for sub-agent handoff decisions.

## ADDED Requirements

### Requirement: Enriched ContextSlice Fields

`ContextSlice` MUST include technical metadata:

- `d4_level`: Current D4 governance level
- `file_hash`: Source file hash for code context
- `task_state`: Current task state
- `token_cost`: Estimated token cost of this slice
- `summary_objective`: User's goal for this context window
- `cache_key`: SHA-256 of operation signature (for cache optimization)
- `cache_hit`: Whether this was a cache hit
- `ttl_seconds`: Remaining TTL if cached

#### Scenario: ContextSlice carries D4 metadata

- GIVEN D4 level is REQUIRED
- WHEN context slice is created for sub-agent handoff
- THEN slice includes `d4_level: "REQUIRED"`, `task_state: "in_progress"`
- AND sub-agent receives context with full technical metadata

### Requirement: Sub-Agent Handoff Format

When passing context to a sub-agent, the system SHALL format ContextSlice as:

```json
{
  "messages": [...],
  "metadata": {
    "d4_level": "REQUIRED",
    "token_budget_remaining": 45000,
    "task_state": "in_progress",
    "file_hash": "abc123",
    "summary_objective": "implement auth middleware"
  }
}
```

#### Scenario: Sub-agent receives enriched context

- GIVEN orchestrator prepares handoff to `sdd-apply`
- WHEN context slice is built
- THEN sub-agent receives messages + metadata block
- AND can make budget decisions based on `token_budget_remaining`

## Edge Cases

### Requirement: Cache Failure Fallback

If cache lookup fails mid-operation, ContextSlice falls back to normal execution without cache metadata.

#### Scenario: Cache corrupted

- GIVEN cache entry exists but is corrupted
- WHEN cache lookup is attempted
- THEN operation executes normally
- AND ContextSlice has `cache_hit: false`, `cache_key: null`