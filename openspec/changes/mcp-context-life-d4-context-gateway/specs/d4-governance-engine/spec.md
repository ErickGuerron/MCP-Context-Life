# Delta for d4-governance-engine

## Purpose

D4 Context Gateway governance engine that determines intervention level based on context health.

## ADDED Requirements

### Requirement: D4 Level Detection

The system SHALL analyze the current context window and determine the appropriate D4 level:

| Level | Condition | Action |
|-------|-----------|--------|
| NOP | tokens < 2000 | No intervention |
| LIGHT | 5 ≤ messages < 15 | Basic summary of recent messages |
| REQUIRED | 15 ≤ messages < 50 | Metadata filter + summary_objective application |
| CRITICAL | messages ≥ 50 OR tokens > 80% budget | History purge + essential state re-injection |

#### Scenario: NOP level applied

- GIVEN context has < 2000 tokens
- WHEN `analyze_context_health` is called
- THEN `d4_level: "NOP"` is returned
- AND no intervention is performed

#### Scenario: REQUIRED level applied

- GIVEN context has 20 messages and 15000 tokens
- WHEN `analyze_context_health` is called
- THEN `d4_level: "REQUIRED"` is returned
- AND metadata filtering is triggered

### Requirement: D4 Hint Export

The system SHALL expose D4 level and hints to the orchestrator via `OrchestratorInfo.d4_hints`.

The `d4_hints` field MUST contain:
- `level`: current D4 level (NOP/LIGHT/REQUIRED/CRITICAL)
- `tokens_used`: current token count
- `tokens_budget`: configured budget
- `budget_percentage`: tokens_used / tokens_budget
- `message_count`: number of messages in context
- `should_trim_now`: boolean
- `suggested_strategy`: trim strategy recommendation

#### Scenario: D4 hints exposed

- GIVEN D4 level is CRITICAL
- WHEN orchestrator calls `get_orchestrator_info()`
- THEN `d4_hints` includes `level: "CRITICAL"`, `should_trim_now: true`

## Edge Cases

### Requirement: Rapid Level Transition

If context transitions from LIGHT to CRITICAL within the same session, the system MUST immediately apply CRITICAL actions.

#### Scenario: Rapid escalation

- GIVEN D4 level was LIGHT
- WHEN 30 new messages are added in one batch
- THEN D4 level becomes CRITICAL immediately
- AND purge action is applied

### Requirement: D4 Level Stability

NOP and LIGHT levels should remain stable for at least 5 message exchanges before escalating.

#### Scenario: Level stability at NOP

- GIVEN D4 level is NOP
- WHEN 3 new messages are added
- THEN D4 level remains NOP
- AND no intervention is triggered