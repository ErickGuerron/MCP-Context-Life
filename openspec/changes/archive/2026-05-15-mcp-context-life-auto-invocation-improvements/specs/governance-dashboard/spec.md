# Delta for governance-dashboard

Extends `openspec/specs/operations/rfc-session-cache-and-usage-tui-v1.md`

## ADDED Requirements

### Requirement: Governance Status Panel

The TUI SHALL display a governance status panel showing:

- Current governance priority level (low, medium, high, critical)
- Active trigger count
- Recent governance alerts (last 5)
- Governance skill version and status

#### Scenario: Dashboard shows governance panel

- GIVEN the governance dashboard is active
- WHEN the user navigates to the governance view
- THEN the governance status panel is displayed
- AND all metrics are current as of last evaluation

### Requirement: Auto-Invoke Cache Metrics Display

The TUI SHALL display auto-invoke cache metrics:

- Cache hit rate (percentage)
- Total cache hits / total cache requests
- Tokens saved via cache
- Current cache size (entries)

#### Scenario: Cache metrics displayed

- GIVEN auto-invoke cache is enabled
- WHEN the dashboard loads
- THEN cache metrics are visible
- AND updated in real-time or near-real-time

### Requirement: Session Health Indicators

The dashboard SHALL display session health indicators:

- Session age (time since first message)
- Context token count vs budget threshold
- Cache warm/cold/prewarmed status
- Active governance triggers

#### Scenario: Cold session shows cold indicator

- GIVEN a session is cold (no persisted state restored)
- WHEN the dashboard displays session health
- THEN it shows `Status: Cold`
- AND recommends prewarm if applicable

### Requirement: Governance Dashboard Toggle

The dashboard MUST be hideable via config:

- `governance_dashboard.enabled: false` — dashboard hidden from TUI

#### Scenario: Hidden dashboard not accessible

- GIVEN `governance_dashboard.enabled` is `false`
- WHEN the user attempts to access governance dashboard
- THEN the view is not available
- AND a message indicates it is disabled

## Edge Cases

### Requirement: Dashboard Load Failure Handling

The system MUST handle gracefully when dashboard cannot load due to data unavailability.

#### Scenario: No data shows placeholder

- GIVEN no usage data is available yet
- WHEN the dashboard loads
- THEN placeholder text is shown: "No data available yet"
- AND the dashboard does not crash

### Requirement: Stale Metrics Display

The dashboard MUST indicate when metrics are stale (not updated within configured threshold).

#### Scenario: Stale metrics flagged

- GIVEN metrics have not been updated in 60 seconds
- WHEN the dashboard renders
- THEN a `staleness` indicator is shown
- AND timestamp of last update is displayed