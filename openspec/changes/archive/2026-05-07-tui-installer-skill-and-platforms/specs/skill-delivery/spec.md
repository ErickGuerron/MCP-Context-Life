# Delta for Skill Delivery

## Purpose

Extend the Context-Life TUI installer to deliver the `context-life-integration` skill to OpenCode and Antigravity platforms, and configure VS Code for MCP access only — giving users a first-class setup experience across three existing platforms.

## ADDED Requirements

### Requirement: Skill Source Location

The installer MUST locate the `context-life-integration` skill source via `get_skill_source_path()` which MUST return an absolute path to the skill's `SKILL.md` file.

The system SHALL raise `FileNotFoundError` with a clear message if the skill source cannot be located at the expected path.

#### Scenario: Skill source found

- GIVEN the installer package includes `context-life-integration` skill
- WHEN `get_skill_source_path()` is called
- THEN it returns a valid absolute path to `SKILL.md`
- AND the returned path ends with `context-life-integration/SKILL.md`

#### Scenario: Skill source missing

- GIVEN the skill is not bundled with the installer
- WHEN `get_skill_source_path()` is called
- THEN `FileNotFoundError` is raised
- AND the error message identifies the expected source location

### Requirement: OpenCode Skill Copy

For the `opencode` target, the installer MUST copy the `context-life-integration` skill to `~/.config/opencode/skills/context-life-integration/` using `shutil.copytree` with `dirs_exist_ok=True`.

The system SHALL preserve the entire skill directory structure during copy.

#### Scenario: OpenCode skill copy succeeds

- GIVEN skill source exists at the resolved path
- WHEN `copy_skill_to_opencode(home_dir)` is called with valid home directory
- THEN `~/.config/opencode/skills/context-life-integration/` is created
- AND all skill files are present at the destination

#### Scenario: OpenCode skill copy overwrites existing

- GIVEN OpenCode skills directory already contains a previous version of `context-life-integration`
- WHEN `copy_skill_to_opencode(home_dir)` is called
- THEN the existing skill directory is replaced entirely
- AND no error is raised due to `dirs_exist_ok=True`

### Requirement: Antigravity Skill Copy

For the `antigravity` target, the installer MUST copy the `context-life-integration` skill to `~/.gemini/skills/context-life-integration/` using `shutil.copytree` with `dirs_exist_ok=True`.

The system SHALL create parent directories with `mkdir(parents=True, exist_ok=True)` before copying if they do not exist.

#### Scenario: Antigravity skill copy succeeds

- GIVEN skill source exists at the resolved path
- WHEN `copy_skill_to_antigravity(home_dir)` is called
- THEN `~/.gemini/skills/context-life-integration/` is created
- AND all skill files are present at the destination

#### Scenario: Antigravity skills directory does not exist

- GIVEN `~/.gemini/skills/` does not exist
- WHEN `copy_skill_to_antigravity(home_dir)` is called
- THEN parent directories are created automatically
- AND copy proceeds without error

### Requirement: VS Code MCP-Only Handling

For the `vscode` target, the installer MUST NOT attempt to copy any skill files. Only the MCP server entry in `mcp.json` SHALL be written.

The system SHALL skip skill copy operations entirely for VS Code targets.

#### Scenario: VS Code install skips skill copy

- GIVEN target is `vscode`
- WHEN the install process reaches skill copy phase
- THEN no skill files are written to any VS Code location
- AND only MCP configuration is updated

### Requirement: Installation Verification

The system MUST provide `verify_install(target, home_dir) -> bool` which checks:
- MCP entry exists in platform config
- For `opencode` and `antigravity`: skill directory exists at destination
- Returns `True` if all conditions are met, `False` otherwise

The CLI MUST call `verify_install()` after `install_context_life()` returns.

#### Scenario: OpenCode verification passes

- GIVEN OpenCode install completed successfully
- WHEN `verify_install('opencode', home_dir)` is called
- THEN MCP entry exists in `~/.config/opencode/settings.json` or equivalent
- AND `~/.config/opencode/skills/context-life-integration/` exists
- AND the function returns `True`

#### Scenario: OpenCode verification fails — skill missing

- GIVEN OpenCode MCP install succeeded but skill copy failed
- WHEN `verify_install('opencode', home_dir)` is called
- THEN skill directory does not exist at expected path
- AND the function returns `False`

#### Scenario: VS Code verification passes

- GIVEN VS Code install completed
- WHEN `verify_install('vscode', home_dir)` is called
- THEN MCP entry exists in `mcp.json`
- AND the function returns `True` (no skill directory check for VS Code)

## ADDED Capabilities

| Capability | Description |
|------------|-------------|
| `skill-delivery` | Copy `context-life-integration` skill to OpenCode and Antigravity skills directories after MCP installation; VS Code receives MCP config only |