# Proposal: tui-installer-skill-and-platforms

## Intent

Extend the Context-Life TUI installer to deliver the `context-life-integration` skill to OpenCode and Antigravity platforms, and configure VS Code for MCP access only — giving users a first-class setup experience across the existing three platforms without adding new install targets.

## Scope

### In Scope
- Add skill copy mechanism to `context_life_installer.py` (source: `context-life-integration` skill)
- Copy skill to OpenCode skills dir (`~/.config/opencode/skills/`)
- Copy skill to Antigravity skills dir (`~/.gemini/skills/`)
- VS Code: configure MCP only (no native skill system to populate)
- TUI menu stays with 3 options (OpenCode, Antigravity, VS Code)
- `verify_install(target, home_dir) -> bool` to confirm skill is present

### Out of Scope
- Adding new install platforms beyond the existing 3
- Modifying MCP server internals or tool behavior
- Changes to RAG, cache, or telemetry subsystems
- Creating the `context-life-integration` skill itself — it is pre-existing and must be delivered as-is

## Capabilities

### New Capabilities
- `skill-delivery`: Copy `context-life-integration` skill to OpenCode and Antigravity skills directories after MCP installation; VS Code receives MCP config only

### Modified Capabilities
- None

## Approach

1. **Skill source detection** — Locate `context-life-integration` SKILL.md in the installer package or via a known path resolver (`get_skill_source_path()`).

2. **Skill copy for OpenCode** — `copy_skill_to_opencode(home_dir)` uses `shutil.copytree` with `dirs_exist_ok=True` to copy the skill to `~/.config/opencode/skills/context-life-integration/`.

3. **Skill copy for Antigravity** — `copy_skill_to_antigravity(home_dir)` copies to `~/.gemini/skills/context-life-integration/`.

4. **VS Code handling** — No skill copy; only MCP entry is written to `mcp.json`.

5. **Verification** — `verify_install(target, home_dir)` checks:
   - MCP entry exists in platform config
   - For OpenCode/Antigravity: skill directory exists at destination
   - Returns `True` if both conditions met, `False` otherwise

6. **TUI menu unchanged** — Existing 3-item menu remains; only the install logic gains skill-copy steps.

## Affected Areas

| Area | Impact | Description |
|------|--------|-------------|
| `mmcp/infrastructure/installation/context_life_installer.py` | Modified | Add `get_skill_source_path()`, `copy_skill_to_opencode()`, `copy_skill_to_antigravity()`, `verify_install()`; call skill copy after MCP install for each platform |
| `mmcp/presentation/cli/cli.py` | Modified | Call `verify_install()` after `install_context_life()` in `_install_context_life_and_return()` |
| `openspec/changes/tui-installer-skill-and-platforms/` | Updated | Proposal, tasks, spec artifacts |

## Risks

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| Skill source not found | Low | Raise `FileNotFoundError` with clear message; do not silently skip |
| Permission errors writing to skills dirs | Low | Catch errors, report path, continue with remaining platforms |
| Antigravity skills dir doesn't exist | Medium | Create parent dirs with `mkdir(parents=True, exist_ok=True)` before copy |
| VS Code has no native skill system | N/A | Documented as expected — no action needed |

## Rollback Plan

1. Remove `get_skill_source_path()`, `copy_skill_to_opencode()`, `copy_skill_to_antigravity()`, and `verify_install()` from `context_life_installer.py`
2. Remove `verify_install` call from `cli.py`
3. Delete `~/.config/opencode/skills/context-life-integration/` and `~/.gemini/skills/context-life-integration/` if present
4. No backup needed — skill is separately managed and can be re-delivered

## Dependencies

- `context-life-integration` skill must exist at a detectable source path (bundled with installer or discovered via standard locations)

## Success Criteria

- [ ] OpenCode receives `context-life-integration` skill in `~/.config/opencode/skills/`
- [ ] Antigravity receives `context-life-integration` skill in `~/.gemini/skills/`
- [ ] VS Code receives only MCP entry (no skill copy attempted)
- [ ] `verify_install()` returns `True` when skill is present, `False` when missing
- [ ] TUI menu shows exactly 3 platforms (no new entries added)
- [ ] Existing platforms (OpenCode, Antigravity, VS Code) continue to work without regression