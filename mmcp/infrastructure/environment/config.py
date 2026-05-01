"""
Config Module ΓÇö Context-Life (CL)

Runtime configuration layer with three-tier resolution:
  1. Built-in defaults (always available)
  2. Config file: ~/.config/context-life/config.toml
  3. Environment variable overrides (CL_* prefix)

These knobs tune performance, storage, and local resource usage.
They MUST NOT silently alter the semantic contract of tool outputs.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

# Attempt TOML import (stdlib in 3.11+, otherwise fallback)
try:
    import tomllib  # Python 3.11+
except ImportError:
    try:
        import tomli as tomllib  # type: ignore[no-redef]
    except ImportError:
        tomllib = None  # type: ignore[assignment]


def _default_config_path() -> Path:
    """Platform-appropriate config file location."""
    if os.name == "nt":
        base = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming"))
    else:
        base = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
    return base / "context-life" / "config.toml"


def _default_data_path() -> Path:
    """Platform-appropriate data directory for LanceDB and caches."""
    if os.name == "nt":
        base = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
    else:
        base = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share"))
    return base / "context-life"


VALID_RAG_WARMUP_MODES = ("lazy", "startup", "manual")


def normalize_rag_warmup_mode(value: object) -> str:
    """Normalize RAG warmup mode values, defaulting safely to lazy."""
    if not isinstance(value, str):
        return "lazy"

    normalized = value.strip().lower()
    if normalized in VALID_RAG_WARMUP_MODES:
        return normalized
    return "lazy"


def get_rag_warmup_mode_details(mode: Optional[str] = None) -> dict:
    """Return UX copy that explains each RAG warmup mode and its MCP impact."""
    current_mode = normalize_rag_warmup_mode(mode)
    modes = {
        "lazy": {
            "label": "Lazy (default)",
            "startup_impact": "Fast MCP startup ΓÇö no embedding model load during boot.",
            "first_use_impact": "First RAG search/index pays the model load cost.",
            "resource_impact": "Lowest idle CPU/RAM usage until RAG is used.",
            "mcp_impact": "Best default for general MCP usage when RAG might not be needed every session.",
        },
        "startup": {
            "label": "Startup",
            "startup_impact": "Slower MCP startup ΓÇö prewarms embeddings during server boot.",
            "first_use_impact": "First RAG search/index is warm and ready sooner.",
            "resource_impact": "Higher upfront CPU/RAM cost because the model loads immediately.",
            "mcp_impact": "Useful when this MCP is expected to serve RAG right away on most sessions.",
        },
        "manual": {
            "label": "Manual",
            "startup_impact": "Fast MCP startup ΓÇö never prewarms automatically.",
            "first_use_impact": "RAG stays cold until you explicitly prewarm or perform the first RAG action.",
            "resource_impact": "Keeps idle resource usage low and gives the user explicit control.",
            "mcp_impact": "Best when the operator wants full control over when the MCP spends warmup time.",
        },
    }

    return {
        "current_mode": current_mode,
        "current": {"mode": current_mode, **modes[current_mode]},
        "modes": modes,
    }


def _toml_literal(value: object) -> str:
    """Serialize a primitive Python value into TOML syntax."""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value)
    return json.dumps(str(value))


def _section_value(data: dict, section: str, key: str) -> object:
    """Safely read a nested TOML section value."""
    section_data = data.get(section, {})
    if isinstance(section_data, dict):
        return section_data.get(key)
    return None


def save_config(
    config: "CLConfig",
    config_path: Optional[str] = None,
    *,
    persist_runtime_paths: bool = False,
) -> Path:
    """Persist the current configuration to TOML.

    By default, writes to the real user config preserve any already-persisted
    path settings instead of serializing transient in-memory overrides. This
    prevents tests/helper flows from leaking temporary pytest paths into the
    user's real config.toml when they only intended to save another setting.
    """
    path = Path(config_path) if config_path else _default_config_path()
    path.parent.mkdir(parents=True, exist_ok=True)

    existing = _load_toml(path)
    preserve_existing_paths = config_path is None and not persist_runtime_paths

    rag_db_path = config.rag_db_path
    cache_db_path = config.cache_db_path
    data_dir = config.data_dir

    if preserve_existing_paths:
        rag_db_path = _section_value(existing, "rag", "db_path") or ""
        cache_db_path = _section_value(existing, "cache", "db_path") or ""
        data_dir = _section_value(existing, "paths", "data_dir") or ""

    sections = [
        (
            "rag",
            {
                "db_path": rag_db_path,
                "table_name": config.rag_table_name,
                "top_k": config.rag_top_k,
                "min_score": config.rag_min_score,
                "max_chunks_per_source": config.rag_max_chunks_per_source,
                "chunk_size": config.rag_chunk_size,
                "chunk_overlap": config.rag_chunk_overlap,
                "warmup_mode": normalize_rag_warmup_mode(config.rag_warmup_mode),
            },
        ),
        (
            "token_budget",
            {
                "default": config.token_budget_default,
                "safety_buffer": config.token_budget_safety_buffer,
            },
        ),
        ("trim", {"preserve_recent": config.trim_preserve_recent}),
        (
            "cache",
            {
                "max_entries": config.cache_max_entries,
                "db_path": cache_db_path,
                "rag_thrash_threshold": config.cache_rag_thrash_threshold,
                "rag_bypass_cooldown": config.cache_rag_bypass_cooldown,
            },
        ),
        ("paths", {"data_dir": data_dir}),
        ("upgrade", {"github_repo": config.github_repo}),
    ]

    lines: list[str] = []
    for section, values in sections:
        filtered_values = {key: value for key, value in values.items() if value not in (None, "")}
        if not filtered_values:
            continue
        lines.append(f"[{section}]")
        for key, value in filtered_values.items():
            lines.append(f"{key} = {_toml_literal(value)}")
        lines.append("")

    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
    return path


@dataclass
class CLConfig:
    """Context-Life runtime configuration."""

    # --- RAG Engine ---
    rag_db_path: str = ""  # Empty = auto (data_dir/lancedb)
    rag_table_name: str = "cl_knowledge"
    rag_top_k: int = 5
    rag_min_score: float = 0.0
    rag_max_chunks_per_source: int = 0
    rag_chunk_size: int = 512
    rag_chunk_overlap: int = 64
    rag_warmup_mode: str = "lazy"

    # --- Token Budget ---
    token_budget_default: int = 128000
    token_budget_safety_buffer: int = 500

    # --- Trim History ---
    trim_preserve_recent: int = 6

    # --- Cache ---
    cache_max_entries: int = 50
    cache_db_path: str = ""  # Empty = auto (data_dir/session.db)
    cache_rag_thrash_threshold: int = 3
    cache_rag_bypass_cooldown: int = 2

    # --- Paths ---
    data_dir: str = ""  # Empty = auto-resolved

    # --- Upgrade ---
    github_repo: str = "ErickGuerron/MCP-Context-Life"

    def resolve_data_dir(self) -> Path:
        """Resolve the data directory, creating it if needed."""
        if self.data_dir:
            p = Path(self.data_dir)
        else:
            p = _default_data_path()
        p.mkdir(parents=True, exist_ok=True)
        return p

    def resolve_rag_db_path(self) -> str:
        """Resolve the LanceDB path."""
        if self.rag_db_path:
            return self.rag_db_path
        return str(self.resolve_data_dir() / "lancedb")

    def resolve_cache_db_path(self) -> Path:
        """Resolve the SQLite session database path."""
        if self.cache_db_path:
            return Path(self.cache_db_path)
        return self.resolve_data_dir() / "session.db"


def _env_override(config: CLConfig) -> None:
    """Apply CL_* environment variable overrides."""
    env_map = {
        "CL_RAG_DB_PATH": ("rag_db_path", str),
        "CL_RAG_TABLE_NAME": ("rag_table_name", str),
        "CL_RAG_TOP_K": ("rag_top_k", int),
        "CL_RAG_MIN_SCORE": ("rag_min_score", float),
        "CL_RAG_MAX_CHUNKS_PER_SOURCE": ("rag_max_chunks_per_source", int),
        "CL_RAG_CHUNK_SIZE": ("rag_chunk_size", int),
        "CL_RAG_CHUNK_OVERLAP": ("rag_chunk_overlap", int),
        "CL_RAG_WARMUP_MODE": ("rag_warmup_mode", str),
        "CL_TOKEN_BUDGET_DEFAULT": ("token_budget_default", int),
        "CL_TOKEN_BUDGET_SAFETY_BUFFER": ("token_budget_safety_buffer", int),
        "CL_TRIM_PRESERVE_RECENT": ("trim_preserve_recent", int),
        "CL_CACHE_MAX_ENTRIES": ("cache_max_entries", int),
        "CL_CACHE_DB_PATH": ("cache_db_path", str),
        "CL_CACHE_RAG_THRASH_THRESHOLD": ("cache_rag_thrash_threshold", int),
        "CL_CACHE_RAG_BYPASS_COOLDOWN": ("cache_rag_bypass_cooldown", int),
        "CL_DATA_DIR": ("data_dir", str),
        "CL_GITHUB_REPO": ("github_repo", str),
    }

    for env_key, (attr, cast) in env_map.items():
        val = os.environ.get(env_key)
        if val is not None:
            try:
                setattr(config, attr, cast(val))
            except (ValueError, TypeError):
                pass  # Silently ignore bad env values

    config.rag_warmup_mode = normalize_rag_warmup_mode(config.rag_warmup_mode)


def _load_toml(path: Path) -> dict:
    """Load a TOML file, returning empty dict if not found or parse fails."""
    if tomllib is None or not path.exists():
        return {}
    try:
        with open(path, "rb") as f:
            return tomllib.load(f)
    except Exception:
        return {}


def load_config(config_path: Optional[str] = None) -> CLConfig:
    """
    Load configuration with three-tier resolution:
    1. Built-in defaults
    2. TOML config file
    3. Environment variable overrides (highest priority)
    """
    config = CLConfig()

    # Tier 2: Config file
    path = Path(config_path) if config_path else _default_config_path()
    data = _load_toml(path)

    if data:
        rag = data.get("rag", {})
        for key in (
            "db_path",
            "table_name",
            "top_k",
            "min_score",
            "max_chunks_per_source",
            "chunk_size",
            "chunk_overlap",
        ):
            if key in rag:
                setattr(config, f"rag_{key}", rag[key])
        if "warmup_mode" in rag:
            config.rag_warmup_mode = normalize_rag_warmup_mode(rag["warmup_mode"])

        token = data.get("token_budget", {})
        if "default" in token:
            config.token_budget_default = token["default"]
        if "safety_buffer" in token:
            config.token_budget_safety_buffer = token["safety_buffer"]

        trim_cfg = data.get("trim", {})
        if "preserve_recent" in trim_cfg:
            config.trim_preserve_recent = trim_cfg["preserve_recent"]

        cache_cfg = data.get("cache", {})
        if "max_entries" in cache_cfg:
            config.cache_max_entries = cache_cfg["max_entries"]
        if "db_path" in cache_cfg:
            config.cache_db_path = cache_cfg["db_path"]
        if "rag_thrash_threshold" in cache_cfg:
            config.cache_rag_thrash_threshold = cache_cfg["rag_thrash_threshold"]
        if "rag_bypass_cooldown" in cache_cfg:
            config.cache_rag_bypass_cooldown = cache_cfg["rag_bypass_cooldown"]

        paths = data.get("paths", {})
        if "data_dir" in paths:
            config.data_dir = paths["data_dir"]

        upgrade = data.get("upgrade", {})
        if "github_repo" in upgrade:
            config.github_repo = upgrade["github_repo"]

    # Tier 3: Environment overrides (highest priority)
    _env_override(config)
    config.rag_warmup_mode = normalize_rag_warmup_mode(config.rag_warmup_mode)

    return config


# Module-level singleton ΓÇö lazy initialized
_config: Optional[CLConfig] = None


def get_config() -> CLConfig:
    """Get the global config singleton."""
    global _config
    if _config is None:
        _config = load_config()
    return _config


def reset_config() -> None:
    """Reset config singleton (for testing)."""
    global _config
    _config = None
