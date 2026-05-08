from __future__ import annotations

import json
import logging
import os
import shutil
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable


logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class InstallTarget:
    key: str
    label: str
    path_resolver: Callable[[Path], Path]
    overlay: dict[str, Any]


@dataclass(frozen=True, slots=True)
class InstallResult:
    key: str
    label: str
    path: Path
    changed: bool


def _opencode_path(home: Path) -> Path:
    return home / ".config" / "opencode" / "opencode.json"


def _antigravity_path(home: Path) -> Path:
    return home / ".gemini" / "antigravity" / "mcp_config.json"


def _antigravity_overlay() -> dict[str, Any]:
    return {
        "mcpServers": {
            "context-life": {
                "command": sys.executable,
                "args": ["-m", "mmcp"],
            }
        }
    }


def _vscode_path(home: Path) -> Path:
    if os.name == "nt":
        appdata = Path(os.environ.get("APPDATA", home / "AppData" / "Roaming"))
        return appdata / "Code" / "User" / "mcp.json"

    if sys_platform() == "darwin":
        return home / "Library" / "Application Support" / "Code" / "User" / "mcp.json"

    xdg = os.environ.get("XDG_CONFIG_HOME")
    base = Path(xdg) if xdg else home / ".config"
    return base / "Code" / "User" / "mcp.json"


def sys_platform() -> str:
    return os.uname().sysname.lower() if hasattr(os, "uname") else os.name


TARGETS: tuple[InstallTarget, ...] = (
    InstallTarget(
        key="opencode",
        label="OpenCode",
        path_resolver=_opencode_path,
        overlay={
            "mcp": {
                "context-life": {
                    "type": "local",
                    "command": ["context-life"],
                    "enabled": True,
                }
            }
        },
    ),
    InstallTarget(
        key="antigravity",
        label="Antigravity",
        path_resolver=_antigravity_path,
        overlay=_antigravity_overlay(),
    ),
    InstallTarget(
        key="vscode",
        label="Visual Studio Code",
        path_resolver=_vscode_path,
        overlay={
            "servers": {
                "context-life": {
                    "type": "stdio",
                    "command": sys.executable,
                    "args": ["-m", "mmcp"],
                }
            }
        },
    ),
)


def get_targets() -> tuple[InstallTarget, ...]:
    return TARGETS


def get_target(key: str) -> InstallTarget:
    normalized = key.strip().lower()
    for target in TARGETS:
        if target.key == normalized:
            return target
    raise KeyError(f"Unknown installation target: {key}")


def get_skill_source_dir() -> Path:
    """Return path to the bundled context-life-integration skill directory.

    Uses importlib.resources to locate the skill bundled in the package.
    Returns a Path object that can be used with shutil.copytree.
    Raises FileNotFoundError if the bundled skill is missing.
    """
    try:
        from importlib.resources import files

        pkg_path = files("mmcp.infrastructure.installation.context-life-integration")
        # MultiplexedPath doesn't have .exists() - use joinpath + resolve instead
        skill_file = pkg_path.joinpath("SKILL.md").resolve()

        if not skill_file.exists():
            raise FileNotFoundError(
                f"Bundled skill 'context-life-integration' is missing SKILL.md at {skill_file}"
            )

        # Return parent directory (the skill directory itself)
        return skill_file.parent
    except FileNotFoundError:
        raise
    except Exception as exc:
        raise FileNotFoundError(
            f"Bundled skill 'context-life-integration' not found in package.\n"
            f"Error: {exc}\n\n"
            "This may indicate the package was not built correctly.\n"
            "Ensure [tool.setuptools.package-data] includes the skill directory."
        )


def copy_skill_to_opencode(home: Path) -> None:
    """Copy context-life-integration skill to OpenCode skills directory.

    Uses shutil.copytree with dirs_exist_ok=True so repeated runs overwrite
    without error. Logs when skill is already present.
    """
    source = get_skill_source_dir()
    dest = home / ".config" / "opencode" / "skills" / "context-life-integration"
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists():
        logger.info("OpenCode skill already present at %s — overwriting.", dest)
    shutil.copytree(source, dest, dirs_exist_ok=True)


def copy_skill_to_antigravity(home: Path) -> None:
    """Copy context-life-integration skill to Antigravity skills directory.

    Creates parent directories with mkdir(parents=True, exist_ok=True) before copy.
    Uses shutil.copytree with dirs_exist_ok=True so repeated runs overwrite without error.
    """
    source = get_skill_source_dir()
    dest = home / ".gemini" / "skills" / "context-life-integration"
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(source, dest, dirs_exist_ok=True)


def install_skill_for_target(target_key: str, home_dir: Path) -> None:
    """Dispatch skill copy to the correct platform handler.

    Raises FileNotFoundError if skill source cannot be located.
    Raises ValueError for unknown targets.
    VS Code is skipped — no skill system available.
    """
    if target_key == "opencode":
        copy_skill_to_opencode(home_dir)
    elif target_key == "antigravity":
        copy_skill_to_antigravity(home_dir)
    elif target_key == "vscode":
        # VS Code has no skill system — MCP only
        pass
    else:
        raise ValueError(f"Unknown installation target: {target_key}")


def verify_install(target_key: str, home_dir: Path) -> tuple[bool, bool, str]:
    """Check that installation succeeded for the given target.

    Returns (mcp_ok, skill_ok, message):
    - mcp_ok: MCP entry exists in platform config
    - skill_ok: skill directory exists (True for VS Code since no skill needed)
    - message: human-readable status line
    """
    target = get_target(target_key)
    config_path = target.path_resolver(home_dir)
    mcp_ok = config_path.exists() and _read_json_object(config_path) != {}

    if target_key == "vscode":
        return (mcp_ok, True, "VS Code MCP configured (no skill system).")

    skill_dest = None
    if target_key == "opencode":
        skill_dest = home_dir / ".config" / "opencode" / "skills" / "context-life-integration"
    elif target_key == "antigravity":
        skill_dest = home_dir / ".gemini" / "skills" / "context-life-integration"

    skill_ok = skill_dest is not None and skill_dest.exists()

    if mcp_ok and skill_ok:
        return (True, True, f"{target.label}: MCP and skill installed.")
    elif mcp_ok and not skill_ok:
        return (True, False, f"{target.label}: MCP OK, skill missing.")
    else:
        return (False, False, f"{target.label}: MCP config missing.")


def install_context_life(target_key: str, home_dir: str | Path | None = None) -> InstallResult:
    home = Path(home_dir) if home_dir is not None else Path.home()
    target = get_target(target_key)
    path = target.path_resolver(home)
    base = _read_json_object(path)
    merged = _deep_merge(base, target.overlay)

    # Always try to copy skill if platform supports it, even when MCP config unchanged
    skill_changed = False
    try:
        install_skill_for_target(target_key, home)
        skill_changed = True
    except Exception as exc:
        logger.warning("Skill copy failed for %s: %s", target_key, exc)

    if base == merged:
        return InstallResult(key=target.key, label=target.label, path=path, changed=False)

    _write_json_atomic(path, merged)
    return InstallResult(key=target.key, label=target.label, path=path, changed=True)


def _read_json_object(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}

    raw = path.read_text(encoding="utf-8")
    if not raw.strip():
        return {}

    for candidate in (raw, _strip_trailing_commas(_strip_json_comments(raw))):
        try:
            loaded = json.loads(candidate)
        except json.JSONDecodeError:
            continue
        if isinstance(loaded, dict):
            return loaded

    return {}


def _strip_json_comments(raw: str) -> str:
    out: list[str] = []
    in_string = False
    escaped = False
    in_line_comment = False
    in_block_comment = False

    i = 0
    while i < len(raw):
        ch = raw[i]

        if in_line_comment:
            if ch == "\n":
                in_line_comment = False
                out.append(ch)
            i += 1
            continue

        if in_block_comment:
            if ch == "*" and i + 1 < len(raw) and raw[i + 1] == "/":
                in_block_comment = False
                i += 2
                continue
            i += 1
            continue

        if in_string:
            out.append(ch)
            if escaped:
                escaped = False
            elif ch == "\\":
                escaped = True
            elif ch == '"':
                in_string = False
            i += 1
            continue

        if ch == '"':
            in_string = True
            out.append(ch)
            i += 1
            continue

        if ch == "/" and i + 1 < len(raw):
            next_ch = raw[i + 1]
            if next_ch == "/":
                in_line_comment = True
                i += 2
                continue
            if next_ch == "*":
                in_block_comment = True
                i += 2
                continue

        out.append(ch)
        i += 1

    return "".join(out)


def _strip_trailing_commas(raw: str) -> str:
    out: list[str] = []
    in_string = False
    escaped = False
    i = 0
    while i < len(raw):
        ch = raw[i]

        if in_string:
            out.append(ch)
            if escaped:
                escaped = False
            elif ch == "\\":
                escaped = True
            elif ch == '"':
                in_string = False
            i += 1
            continue

        if ch == '"':
            in_string = True
            out.append(ch)
            i += 1
            continue

        if ch == ",":
            j = i + 1
            while j < len(raw) and raw[j] in " \t\n\r":
                j += 1
            if j < len(raw) and raw[j] in "}]":
                i += 1
                continue

        out.append(ch)
        i += 1

    return "".join(out)


def _deep_merge(base: dict[str, Any], overlay: dict[str, Any]) -> dict[str, Any]:
    result = dict(base)
    for key, value in overlay.items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def _write_json_atomic(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(payload, indent=2, ensure_ascii=False) + "\n"
    with tempfile.NamedTemporaryFile(
        "w", encoding="utf-8", delete=False, dir=path.parent, prefix=path.name, suffix=".tmp"
    ) as tmp:
        tmp.write(text)
        temp_path = Path(tmp.name)
    temp_path.replace(path)
