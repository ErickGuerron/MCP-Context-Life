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


@dataclass(frozen=True, slots=True)
class ConnectedProvider:
    """A provider the user has connected via auth.json (OAuth/token)."""

    id: str  # e.g. "openai", "anthropic", "google"
    name: str  # display name if available


@dataclass(frozen=True, slots=True)
class LocalModel:
    """A locally configured model (e.g. Ollama running on machine)."""

    provider: str  # e.g. "ollama"
    model_id: str
    full_name: str


def _get_auth_providers(home: Path) -> list[ConnectedProvider]:
    """Read auth.json and return connected providers."""
    auth_path = home / ".local" / "share" / "opencode" / "auth.json"
    if not auth_path.exists():
        return []

    try:
        auth_data = json.loads(auth_path.read_text(encoding="utf-8"))
        providers = []
        for provider_id in auth_data.keys():
            providers.append(ConnectedProvider(id=provider_id, name=provider_id.title()))
        return providers
    except (json.JSONDecodeError, OSError):
        return []


def _get_local_models(home: Path) -> list[LocalModel]:
    """Read opencode.json provider config for local models (e.g. ollama)."""
    opencode_path = home / ".config" / "opencode" / "opencode.json"
    config = _read_json_object(opencode_path)

    local_models: list[LocalModel] = []
    provider_config = config.get("provider", {})

    if isinstance(provider_config, dict):
        for provider_name, provider_data in provider_config.items():
            if not isinstance(provider_data, dict):
                continue
            # Only include providers that have locally hosted models
            # (identified by having a base_url pointing to localhost)
            options = provider_data.get("options", {})
            # Handle both base_url and baseURL (opencode uses camelCase)
            base_url = ""
            if isinstance(options, dict):
                base_url = options.get("base_url", options.get("baseURL", ""))
            is_local = "localhost" in base_url or "127.0.0.1" in base_url

            if is_local:
                provider_models = provider_data.get("models", {})
                if isinstance(provider_models, dict):
                    for model_id in provider_models.keys():
                        local_models.append(
                            LocalModel(
                                provider=provider_name,
                                model_id=model_id,
                                full_name=f"{provider_name}/{model_id}",
                            )
                        )

    return local_models


@dataclass
class StackDetection:
    has_gentle_ai: bool
    has_engram: bool


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

    # On Linux, respect APPDATA if set (e.g. CI test environment)
    appdata = os.environ.get("APPDATA")
    if appdata:
        return Path(appdata) / "Code" / "User" / "mcp.json"

    # Otherwise use XDG_CONFIG_HOME or ~/.config
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
        skill_file = pkg_path.joinpath("SKILL.md").resolve()

        if not skill_file.exists():
            raise FileNotFoundError(f"Bundled skill 'context-life-integration' is missing SKILL.md at {skill_file}")

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
    """Copy context-life-integration skill to OpenCode skills directory."""
    source = get_skill_source_dir()
    dest = home / ".config" / "opencode" / "skills" / "context-life-integration"
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists():
        logger.info("OpenCode skill already present at %s — overwriting.", dest)
    shutil.copytree(source, dest, dirs_exist_ok=True)


def copy_skill_to_antigravity(home: Path) -> None:
    """Copy context-life-integration skill to Antigravity skills directory."""
    source = get_skill_source_dir()
    dest = home / ".gemini" / "skills" / "context-life-integration"
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(source, dest, dirs_exist_ok=True)


def install_skill_for_target(target_key: str, home_dir: Path) -> None:
    """Dispatch skill copy to the correct platform handler."""
    if target_key == "opencode":
        copy_skill_to_opencode(home_dir)
    elif target_key == "antigravity":
        copy_skill_to_antigravity(home_dir)
    elif target_key == "vscode":
        pass
    else:
        raise ValueError(f"Unknown installation target: {target_key}")


def verify_install(target_key: str, home_dir: Path) -> tuple[bool, bool, str]:
    """Check that installation succeeded for the given target."""
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


def detect_stack(home: Path) -> StackDetection:
    """Detect which stack components are available."""
    opencode_path = home / ".config" / "opencode" / "opencode.json"
    config = _read_json_object(opencode_path)

    has_gentle_ai = False
    agents = config.get("agent", {})
    if isinstance(agents, dict):
        has_gentle_ai = "gentle-orchestrator" in agents or "sdd-orchestrator" in agents

    has_engram = False
    mcp = config.get("mcp", {})
    if isinstance(mcp, dict):
        has_engram = any("engram" in k.lower() for k in mcp.keys())

    return StackDetection(has_gentle_ai=has_gentle_ai, has_engram=has_engram)


def _get_advisor_prompt_content(stack: StackDetection) -> str:
    """Generate advisor prompt based on detected stack."""
    base = """# Context-Life Advisor

You are the `context-life-advisor` sub-agent. Your role is to intercept and optimize
context before the orchestrator begins working on a task.

## Workflow

1. Receive a raw user request from the orchestrator
"""

    if stack.has_engram:
        base += """2. Check Engram for conflicting past decisions:
   - Call: engram/mem_search with query about past decisions related to the request
   - If contradiction found → elevate to CRITICAL immediately (skip step 3)
3. If no contradiction, run D4 classification

"""
    else:
        base += """2. Run D4 classification by calling intercept_user_request

"""

    base += """3. Call `intercept_user_request` via bash:
   ```
   python -m mmcp intercept_user_request "YOUR_RAW_REQUEST_HERE"
   ```
4. Parse the JSON response — extract the `d4` object (ContextPack):
   - `d4.state`: LIGHT | REQUIRED | CRITICAL
   - `d4.confidence`: float
   - `d4.project_context`: {stack, architecture, testing, package_manager}
   - `d4.files`: {explicit: [], inferred: []}
   - `d4.constraints`: list
   - `d4.missing_context`: list
   - `d4.next_action`: string
   - `d4.halt`: object with conflict details if CRITICAL

5. Based on `d4.state`, determine context budget:
   - LIGHT = small budget (min tokens to validate paths)
   - REQUIRED = medium (search for missing pieces)
   - CRITICAL = tiny (halt only, no code generation)

"""

    if stack.has_engram:
        base += """## D4 History Awareness (Engram)
If Engram check found a contradiction, format CRITICAL output with:
- The conflicting past decision
- The new request
- Question: "¿Deseas actualizar la decisión anterior o mantenerla?"

"""

    base += """## Output Format

Return a Markdown report to the orchestrator:

## Context Analysis

**State**: [d4.state]
**Confidence**: [d4.confidence]
**Goal**: [extracted from request]

### Project Context
- Stack: [d4.project_context.stack]
- Architecture: [d4.project_context.architecture]
- Testing: [d4.project_context.testing]
- Package Manager: [d4.project_context.package_manager]

### Files
- Explicit: [d4.files.explicit]
- Inferred: [d4.files.inferred]

### Constraints
[d4.constraints]

### Missing Context
[d4.missing_context]

### Next Action
[d4.next_action]

## If CRITICAL (HALT)

"""

    if stack.has_gentle_ai and stack.has_engram:
        base += """⚠️ **HALT REQUIRED** — Conflict with past decisions or detected contradiction
- **Risk**: [d4.halt.risk]
- **Detected Goal**: [d4.halt.detected_goal]
- **Conflict**: [d4.halt.conflict]
- **Required Decision**: [d4.halt.required_decision]
- **Strict TDD Question**: ¿Deseas actualizar la suite de tests de integración para este cambio mayor?

"""
    else:
        base += """⚠️ **HALT REQUIRED**
- **Risk**: [d4.halt.risk]
- **Detected Goal**: [d4.halt.detected_goal]
- **Conflict**: [d4.halt.conflict]
- **Required Decision**: [d4.halt.required_decision]

"""

    base += """## Important

- Do NOT write code — only analyze and report
- Do NOT delegate to other agents
- Return the Markdown report to the orchestrator
"""

    return base


def install_context_life_advisor(home: Path, model: str | None = None) -> dict[str, Any]:
    """Install context-life-advisor sub-agent with stack-aware configuration.

    Args:
        home: User's home directory (Path.home())
        model: Model to use for the advisor (e.g. "ollama/qwen3:8b").
               If None, must be selected interactively via the TUI.

    Returns the updated config dict (in memory) so caller can use it.
    Does NOT write to disk — caller is responsible for writing.
    """
    stack = detect_stack(home)

    # 1. Create advisor prompt file
    prompts_dir = home / ".config" / "opencode" / "prompts"
    prompts_dir.mkdir(parents=True, exist_ok=True)
    advisor_prompt_path = prompts_dir / "context-life-advisor.md"

    content = _get_advisor_prompt_content(stack)
    advisor_prompt_path.write_text(content, encoding="utf-8")

    # 2. Add agent entry to opencode.json
    opencode_path = home / ".config" / "opencode" / "opencode.json"
    config = _read_json_object(opencode_path)

    # Ensure agent dict exists
    if "agent" not in config:
        config["agent"] = {}

    # Add context-life-advisor agent entry (idempotent — won't overwrite existing)
    if "context-life-advisor" not in config["agent"]:
        config["agent"]["context-life-advisor"] = {
            "description": "Intercepts raw user requests to resolve project context and optimize context budgets",
            "hidden": True,
            "mode": "subagent",
            "model": model or "ollama/qwen3:8b",
            "prompt": str(advisor_prompt_path),
            "tools": {"bash": True, "read": True, "write": True},
        }

    # 3. Update sdd-orchestrator.md ONLY if gentle-ai detected
    if stack.has_gentle_ai:
        orchestrator_path = prompts_dir / "sdd" / "sdd-orchestrator.md"
        if orchestrator_path.exists():
            # Read current content
            content = orchestrator_path.read_text(encoding="utf-8")

            # Check if delegation to context-life-advisor already exists
            if "context-life-advisor" not in content:
                # Add delegation before the first SDD workflow section
                insertion = """
## Context-Life Advisor Integration [Auto-Installed]

When a user request arrives, delegate to `context-life-advisor` FIRST to validate context:
- If CRITICAL: HALT and ask user for clarification
- If REQUIRED: Gather missing context before proceeding
- If LIGHT: Proceed with the context provided

To delegate:
```
task description="Analyze user request context" agent="context-life-advisor" prompt="[user's raw request]"
```

"""
                # Insert after the "You are a COORDINATOR" line and before Delegation Rules
                if "You are a COORDINATOR" in content:
                    parts = content.split("You are a COORDINATOR", 1)
                    content = parts[0] + "You are a COORDINATOR" + insertion + parts[1]
                    orchestrator_path.write_text(content, encoding="utf-8")

    return config


def write_advisor_config_to_opencode(home: Path, config: dict[str, Any]) -> None:
    """Write the advisor agent config into opencode.json via atomic write."""
    opencode_path = home / ".config" / "opencode" / "opencode.json"
    _write_json_atomic(opencode_path, config)


def install_context_life(target_key: str, home_dir: str | Path | None = None) -> InstallResult:
    home = Path(home_dir) if home_dir is not None else Path.home()
    target = get_target(target_key)
    path = target.path_resolver(home)
    base = _read_json_object(path)
    merged = _deep_merge(base, target.overlay)

    # Always try to copy skill if platform supports it, even when MCP config unchanged
    try:
        install_skill_for_target(target_key, home)
    except Exception as exc:
        logger.warning("Skill copy failed for %s: %s", target_key, exc)

    # Install context-life-advisor sub-agent for opencode target
    if target_key == "opencode":
        advisor_config = install_context_life_advisor(home)
        # Merge advisor agent entry into merged config so it gets written
        if "agent" not in merged:
            merged["agent"] = {}
        for agent_name, agent_config in advisor_config.get("agent", {}).items():
            if agent_name not in merged["agent"]:
                merged["agent"][agent_name] = agent_config

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
    """Deep merge with special handling for agents array."""
    result = dict(base)
    for key, value in overlay.items():
        if key == "agent" and isinstance(value, dict) and isinstance(result.get(key), dict):
            # Agent-specific merge: append new agents, replacing existing by name
            for agent_name, agent_config in value.items():
                if agent_name in result[key]:
                    # Don't overwrite existing agents
                    continue
                result[key][agent_name] = agent_config
        elif isinstance(value, dict) and isinstance(result.get(key), dict):
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
