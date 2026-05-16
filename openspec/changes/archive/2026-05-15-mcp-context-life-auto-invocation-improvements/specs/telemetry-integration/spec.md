# Delta for telemetry-integration

Extends `openspec/specs/telemetry/RFC-003-telemetry-budget-integrity-and-scalability.md`

## MODIFIED Requirements

### Requirement: Auto-Invoke Event Integration

(Previously: Auto-invoke events not tracked in telemetry pipeline)

The system SHALL integrate auto-invoke events into the existing telemetry pipeline using the RFC-003 schema.

Auto-invoke events MUST follow the canonical `UsageEvent` schema with fields:

- `event_type: auto_invoke`
- `accounting_mode: derived`
- `observed_input_tokens`, `observed_output_tokens`
- `billable_input_tokens`, `billable_output_tokens`
- `saved_tokens`

#### Scenario: Auto-invoke event emitted to telemetry

- GIVEN an auto-invoke completes
- WHEN the operation finishes
- THEN a `UsageEvent` is emitted to the telemetry service
- AND it follows the RFC-003 canonical schema

#### Scenario: Auto-invoke cache hit reduces telemetry overhead

- GIVEN an auto-invoke cache hit occurs
- WHEN the result is returned
- THEN the emitted telemetry event reflects zero execution cost
- AND `saved_tokens` reflects the cached savings

## ADDED Requirements

### Requirement: Async Telemetry Emission

The telemetry emission MUST NOT block the main auto-invoke execution path.

Telemetry events SHALL be emitted asynchronously using a background queue or worker thread.

#### Scenario: Async emission does not affect latency

- GIVEN telemetry is properly configured
- WHEN an auto-invoke completes
- THEN the caller receives the result immediately
- AND telemetry emission happens in background

### Requirement: Telemetry Integration Toggle

The integration MUST be toggleable without affecting other telemetry paths:

- `telemetry.integration.auto_invoke: false` — disables auto-invoke telemetry

#### Scenario: Disabled auto-invoke telemetry

- GIVEN `telemetry.integration.auto_invoke` is `false`
- WHEN an auto-invoke completes
- THEN no telemetry event is emitted for that operation
- AND other telemetry paths remain unaffected

## Edge Cases

### Requirement: Telemetry Service Unavailable

The system MUST handle gracefully when the telemetry service is unavailable.

#### Scenario: Telemetry endpoint unavailable

- GIVEN the telemetry service is unreachable
- WHEN an auto-invoke completes
- THEN the operation succeeds without telemetry
- AND events are optionally queued for later retry
- AND a warning is logged (not an error)

### Requirement: Telemetry Overhead Budget

Auto-invoke telemetry MUST introduce less than 5ms overhead per invocation.

#### Scenario: Overhead measured and within budget

- GIVEN telemetry is enabled
- WHEN an auto-invoke completes with telemetry
- THEN the additional latency from telemetry is measured
- AND must be under 5ms