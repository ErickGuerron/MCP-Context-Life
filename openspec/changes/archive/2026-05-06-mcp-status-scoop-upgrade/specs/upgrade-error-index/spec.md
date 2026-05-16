# upgrade-error-index

## Purpose

Replace the generic upgrade failure panel with granular error classification codes and per-code remediation steps.

## ADDED Requirements

### Requirement: Error Code Classification

The `context-life upgrade` command MUST classify failures into specific error codes after `subprocess.run` fails.

The system SHALL assign one of the following codes:
| Code | Name | Condition |
|------|------|-----------|
| `E01` | Network failure | Connection timeout, DNS failure, connection refused (ECONNREFUSED), HTTPS error |
| `E02` | Permission denied | Write permission failure (EACCES, EPERM) |
| `E03` | PEP 668 externally managed | "externally managed" or "not writable" in stderr |
| `E04` | Version not found | Target package or release not found (404, not on PyPI) |
| `E05` | Checksum mismatch | Downloaded file hash does not match expected |
| `E99` | Unknown error | Fallback for unrecognized failures |

#### Scenario: Network failure

- GIVEN `context-life upgrade` encounters a network outage
- WHEN the subprocess fails
- THEN the system detects the network-related error pattern
- AND displays code `E01` with description "Network failure"
- AND shows remediation: "Check internet connection, proxy settings, or VPN"

#### Scenario: Permission denied

- GIVEN `context-life upgrade` cannot write to the install directory
- WHEN the subprocess fails with permission error
- THEN the system displays code `E02` with description "Permission denied"
- AND shows remediation: "Run as administrator or use --user flag"

#### Scenario: PEP 668 externally managed environment

- GIVEN `context-life upgrade` hits PEP 668 restriction
- WHEN the subprocess fails with externally-managed message
- THEN the system displays code `E03` with description "PEP 668"
- AND shows remediation: "Use `uv tool install` or create a virtual environment"

#### Scenario: Version not found

- GIVEN `context-life upgrade` targets a non-existent version
- WHEN the subprocess fails with 404
- THEN the system displays code `E04` with description "Version not found"
- AND shows remediation: "Verify the version exists on PyPI or GitHub"

#### Scenario: Checksum mismatch

- GIVEN `context-life upgrade` downloads a corrupt file
- WHEN checksum verification fails
- THEN the system displays code `E05` with description "Checksum mismatch"
- AND shows remediation: "Retry the upgrade; if the issue persists, report the bug"

#### Scenario: Unknown error

- GIVEN `context-life upgrade` fails with an unrecognized error
- WHEN the error does not match any known code pattern
- THEN the system displays code `E99` with description "Unknown error"
- AND shows remediation: "Run `context-life doctor` for diagnostics"
- AND includes the raw stderr output

### Requirement: Error Panel Display

Each error code MUST render its own `Panel` with the specific remediation.

The system SHALL NOT show the current generic "install uv" message for any failure.

#### Scenario: Panel contains all required fields

- GIVEN an upgrade failure occurs
- WHEN the error panel is displayed
- THEN it MUST show: error code, description, possible cause, remediation steps
- AND raw stderr MUST be shown for `E99` only

### Requirement: Error Code Parsing

The stderr output MUST be parsed using pattern matching against known error message templates.

The system SHALL apply error codes in priority order:
1. `E03` (PEP 668) — checked first due to specific message matching
2. `E01` (Network)
3. `E02` (Permission)
4. `E04` (Version)
5. `E05` (Checksum)
6. `E99` (Unknown)

#### Scenario: PEP 668 detected among network errors

- GIVEN stderr contains both "externally managed" and network error patterns
- WHEN the parser runs
- THEN `E03` takes precedence
- AND the PEP 668 remediation is shown

#### Scenario: E01 pattern matching

- GIVEN stderr contains "Connection refused"
- WHEN the parser evaluates the error
- THEN `E01` is assigned
- AND network remediation is shown
