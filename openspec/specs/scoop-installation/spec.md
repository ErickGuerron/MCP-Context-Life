# scoop-installation

## Purpose

Create a Scoop bucket manifest for Context-Life enabling `scoop install context-life` on Windows.

## ADDED Requirements

### Requirement: Scoop Manifest Format

The manifest file `bucket/context-life.json` MUST be valid JSON and conform to Scoop's manifest specification.

The system SHALL include the following top-level fields:
- `version`: Semantic version string matching the GitHub release tag
- `url`: Direct URL to the release asset (wheel or installer)
- `hash`: SHA256 hash of the release asset
- `architecture`: Object with `amd64` and `arm64` URLs/hashes
- `bin`: List of executable entry points installed by the manifest

#### Scenario: Happy path installation

- GIVEN a user has Scoop installed on Windows
- WHEN the user adds the bucket and runs `scoop install context-life`
- THEN Scoop downloads the correct release asset for the user's architecture
- AND verifies the hash against the manifest
- AND installs the executable to the shim directory

#### Scenario: Version detection

- GIVEN a user runs `scoop update context-life`
- WHEN the manifest is processed
- THEN the system queries the GitHub releases API for the latest tag
- AND compares it against the installed version
- AND reports whether an update is available

#### Scenario: Architecture selection

- GIVEN a user on ARM64 Windows runs `scoop install context-life`
- WHEN Scoop processes the manifest
- THEN the system uses the arm64 URL and hash fields
- AND the amd64 fields are ignored

### Requirement: Bucket Integration

The bucket URL for `context-life` MUST be a raw GitHub blob URL or a dedicated bucket hosting endpoint.

The system SHALL support `scoop bucket add context-life <bucket-url>` followed by `scoop install context-life`.

#### Scenario: Bucket addition

- GIVEN a user adds the bucket with `scoop bucket add context-life <url>`
- WHEN the command succeeds
- THEN the bucket is listed in `scoop bucket list`
- AND subsequent `scoop install` commands can resolve `context-life`

### Requirement: Update Detection

The manifest MUST support `scoop update context-life` by querying the GitHub releases API.

The system SHALL parse the latest release tag and make it available for Scoop's update logic.

#### Scenario: Update available

- GIVEN Context-Life v1.0.0 is installed
- WHEN GitHub has release v1.1.0
- AND the user runs `scoop update context-life`
- THEN Scoop reports that v1.1.0 is available
- AND offers to upgrade

#### Scenario: No update available

- GIVEN Context-Life v1.1.0 is installed
- WHEN GitHub has release v1.1.0
- AND the user runs `scoop update context-life`
- THEN Scoop reports that no update is available