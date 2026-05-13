# Delta for multi-stack-detection

## ADDED Requirements

### Requirement: Cursor AI Detection

The system SHALL detect Cursor AI as an MCP host via the `CURSOR_DIR` environment variable.

When `CURSOR_DIR` is set and points to a valid directory, the orchestrator detector MUST return `host_type: cursor-ai`.

#### Scenario: Cursor AI detected via environment variable

- GIVEN `CURSOR_DIR` is set to a valid path
- WHEN `get_orchestrator_info()` is called
- THEN `host_type` is `cursor-ai`
- AND `host_name` reflects the detected name

#### Scenario: Cursor AI absent returns not-detected

- GIVEN `CURSOR_DIR` is not set
- WHEN `get_orchestrator_info()` is called
- THEN `host_type` does not include `cursor-ai`

### Requirement: Windsurf Detection

The system SHALL detect Windsurf as an MCP host via the `WINDURF_DATA_DIR` environment variable.

When `WINDURF_DATA_DIR` is set, the orchestrator detector MUST return `host_type: windsurf`.

#### Scenario: Windsurf detected via environment variable

- GIVEN `WINDURF_DATA_DIR` is set
- WHEN `get_orchestrator_info()` is called
- THEN `host_type` is `windsurf`

### Requirement: Codex AI Detection

The system SHALL detect Codex AI via process name matching `codex-cli`.

The detector MUST use process enumeration to identify running Codex CLI processes.

#### Scenario: Codex AI detected via process name

- GIVEN a process named `codex-cli` is running
- WHEN `get_orchestrator_info()` is called
- THEN `host_type` is `codex`
- AND `host_name` reflects the detected name

#### Scenario: No Codex process returns not-detected

- GIVEN no `codex-cli` process is running
- WHEN `get_orchestrator_info()` is called
- THEN `host_type` does not include `codex`

### Requirement: Multi-Stack Detection Configuration

Multi-stack detection MUST be toggleable via config:

- `multi_stack_detection.enabled: false` — disables Cursor, Windsurf, Codex detection

#### Scenario: Disabled detection skips environment checks

- GIVEN `multi_stack_detection.enabled` is `false`
- WHEN `get_orchestrator_info()` is called
- THEN environment variables and process checks are skipped
- AND only base detection applies

## Edge Cases

### Requirement: False Positive Prevention via Multi-Signal Validation

The system MUST validate multi-stack detection against multiple signals before confirming. A single environment variable match is not sufficient to classify a host.

#### Scenario: Single signal does not confirm host

- GIVEN `CURSOR_DIR` is set but no other Cursor indicators exist
- WHEN detection runs
- THEN the system requires additional validation
- AND may mark as `cursor-ai (unconfirmed)` until validated

### Requirement: Process Detection Platform Portability

Process name detection MUST handle platform differences. On Windows, process enumeration may require different APIs than Unix.

#### Scenario: Windows process detection

- GIVEN running on Windows
- WHEN Codex process detection executes
- THEN it uses Windows-compatible process enumeration
- AND correctly identifies `codex-cli.exe` or similar variants

### Requirement: Conflicting Host Detection

When multiple hosts are detected simultaneously (e.g., both Cursor and Windsurf environment variables set), the system MUST prioritize or report all detected hosts.

#### Scenario: Multiple hosts detected

- GIVEN both `CURSOR_DIR` and `WINDURF_DATA_DIR` are set
- WHEN `get_orchestrator_info()` is called
- THEN `host_type` may contain both `cursor-ai` and `windsurf`
- OR the system returns the first matched host with a warning