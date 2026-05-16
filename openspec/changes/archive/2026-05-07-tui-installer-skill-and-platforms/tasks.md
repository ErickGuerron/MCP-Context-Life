# Tasks: tui-installer-skill-and-platforms

## Review Workload Forecast

| Field | Value |
|-------|-------|
| Estimated changed lines | ~80-120 |
| 400-line budget risk | Low |
| Chained PRs recommended | No |
| Suggested split | Single PR |
| Delivery strategy | ask-on-risk |

Decision needed before apply: No
Chained PRs recommended: No
Chain strategy: pending
400-line budget risk: Low

### Suggested Work Units

| Unit | Goal | Likely PR | Notes |
|------|------|-----------|-------|
| 1 | Skill copy mechanism for OpenCode + Antigravity | PR 1 | New functions + integration |
| 2 | `verify_install()` for all 3 platforms | PR 1 | Combined with unit 1 |
| 3 | Wire `verify_install` into TUI flow | PR 1 | Combined with unit 1 |
| 4 | Unit tests for skill copy + verify | PR 1 | Combined with unit 1 |

## Phase 1: Skill Source Resolution

- [x] 1.1 Add `get_skill_source_path() -> Path` in `context_life_installer.py` → returns path to `context-life-integration/SKILL.md` bundled in the installer package

## Phase 2: Skill Copy Implementation

- [x] 2.1 Add `copy_skill_to_opencode(home_dir: Path) -> None` — copies `context-life-integration` to `~/.config/opencode/skills/` using `shutil.copytree` with `dirs_exist_ok=True`; logs skipped if already present
- [x] 2.2 Add `copy_skill_to_antigravity(home_dir: Path) -> None` — copies to `~/.gemini/skills/`; creates parent dirs with `mkdir(parents=True, exist_ok=True)` before copy
- [x] 2.3 Add `install_skill_for_target(target_key: str, home_dir: Path) -> None` — dispatches to `copy_skill_to_opencode` or `copy_skill_to_antigravity` based on target; raises `FileNotFoundError` if skill source not found

## Phase 3: Verification

- [x] 3.1 Add `verify_install(target_key: str, home_dir: Path) -> bool` — checks:
  - MCP entry exists in platform config
  - For OpenCode/Antigravity: skill directory exists at destination
  - Returns `True` if all checks pass, `False` otherwise
- [x] 3.2 Wire `verify_install()` into `_install_context_life_and_return()` in `cli.py` after `install_context_life()` completes; report verification result to user

## Phase 4: Testing

- [x] 4.1 Add `test_get_skill_source_path_returns_bundled_skill()` — verify path resolves to a real SKILL.md
- [x] 4.2 Add `test_copy_skill_to_opencode(tmp_path, monkeypatch)` — verify skill copied to `~/.config/opencode/skills/context-life-integration/`
- [x] 4.3 Add `test_copy_skill_to_antigravity_creates_parent_dirs(tmp_path)` — verify Antigravity copy with dir creation
- [x] 4.4 Add `test_copy_skill_skips_existing(tmp_path)` — verify conflict handling logs and skips
- [x] 4.5 Add `test_install_skill_for_target_dispatches_correctly(tmp_path)` — verify OpenCode vs Antigravity routing
- [x] 4.6 Add `test_verify_install_returns_true_when_skill_present(tmp_path)` — verify OpenCode path with skill + MCP
- [x] 4.7 Add `test_verify_install_returns_false_when_skill_missing(tmp_path)` — verify returns False when skill absent
- [x] 4.8 Add `test_verify_install_vscode_no_skill_check(tmp_path)` — verify VS Code only checks MCP (no skill required)
- [x] 4.9 Add `test_tui_menu_still_has_three_targets()` — verify no new menu entries were added