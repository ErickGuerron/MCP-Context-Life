# Delta for usage-tracking

## ADDED Requirements

### Requirement: Auto-Invoke Event Tracking

The system SHALL track auto-invoke events with the following metrics:

- `auto_invoke_count`: Number of auto-invoke executions
- `auto_invoke_cache_hits`: Number of cache hits
- `tokens_saved_via_cache`: Estimated tokens saved by caching
- `latency_ms`: Time taken for auto-invoke execution

#### Scenario: Auto-invoke increments counter

- GIVEN an auto-invoke executes
- WHEN the operation completes
- THEN `auto_invoke_count` is incremented
- AND `auto_invoke_cache_hit` reflects whether a cache hit occurred

#### Scenario: Cache hit updates savings metric

- GIVEN an auto-invoke cache hit returns a result
- WHEN the result is returned
- THEN `tokens_saved_via_cache` is updated with estimated savings

### Requirement: Per-Host, Per-Agent, Per-Provider, Per-Model Tracking

The system MUST expose metrics broken down by:

- Host: `opencode`, `claude-code`, `cursor-ai`, `windsurf`, `codex`
- Agent: Named agent identifiers
- Provider: `anthropic`, `openai`, `google`, etc.
- Model: Specific model names

#### Scenario: Metrics aggregated by host

- GIVEN multiple auto-invokes from different hosts
- WHEN usage is queried
- THEN metrics are available per `host_name`

### Requirement: MCP Resource Exposure

The system SHALL expose usage summary via MCP resources:

- `usage://overview` — total counts, cache hit rate, tokens saved
- `usage://by-host` — per-host breakdown
- `usage://by-agent` — per-agent breakdown

#### Scenario: Resource returns overview

- GIVEN `usage://overview` is queried
- WHEN the resource handler receives the request
- THEN it returns JSON with total counts, cache hit rate, savings
- AND response is formatted according to RFC-003 schema

### Requirement: Usage Tracking Toggle

Usage tracking MUST be controllable via config:

- `usage_tracking.enabled: false` — disables usage tracking

#### Scenario: Disabled tracking skips metric collection

- GIVEN `usage_tracking.enabled` is `false`
- WHEN auto-invoke executes
- THEN no usage events are recorded
- AND MCP resources return empty or cached data

## Edge Cases

### Requirement: Metric Overhead Mitigation

The system MUST implement async event emission for usage tracking to prevent blocking the main auto-invoke path.

#### Scenario: Async emission does not block invocation

- GIVEN `usage_tracking.enabled` is `true`
- WHEN an auto-invoke completes
- THEN metric emission happens asynchronously
- AND main invocation latency is not affected

### Requirement: Sampling Rate Configuration

The system SHALL support configurable sampling rate to reduce overhead in high-frequency scenarios.

#### Scenario: 10% sampling rate applied

- GIVEN `usage_tracking.sample_rate: 0.1`
- WHEN auto-invoke events occur
- THEN approximately 10% of events are recorded
- AND the sample rate is applied consistently

### Requirement: Partial Event Handling

The system MUST handle partial usage events when host provides incomplete data (e.g., only `model_name` and `input_tokens` known).

#### Scenario: Partial event stored with available fields

- GIVEN a host only provides `model_name` and `input_tokens`
- WHEN the usage event is recorded
- THEN available fields are stored
- AND missing fields default to `null` or `0`
- AND provenance is marked as `estimated`