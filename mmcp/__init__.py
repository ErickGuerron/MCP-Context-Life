"""Context-Life (CL) — LLM Context Optimization MCP Server.

The canonical implementation lives in the visible layer packages
(`mmcp.presentation`, `mmcp.application`, `mmcp.infrastructure`).
This module registers legacy import aliases so external callers that still
refer to `mmcp.token_counter` or `mmcp.server` keep working during migration
without duplicating files.
"""

from __future__ import annotations

import importlib
import sys

__version__ = "0.7.1"


_LEGACY_MODULE_ALIASES = {
    "mmcp.config": "mmcp.infrastructure.environment.config",
    "mmcp.session_store": "mmcp.infrastructure.persistence.session_store",
    "mmcp.cache_manager": "mmcp.infrastructure.persistence.cache_manager",
    "mmcp.orchestrator_detector": "mmcp.infrastructure.environment.orchestrator_detector",
    "mmcp.rag_engine": "mmcp.infrastructure.knowledge.rag_engine",
    "mmcp.trim_history": "mmcp.infrastructure.context.trim_history",
    "mmcp.telemetry_service": "mmcp.infrastructure.telemetry.telemetry_service",
    "mmcp.token_counter": "mmcp.infrastructure.tokens.token_counter",
    "mmcp.app_container": "mmcp.presentation.app_container",
    "mmcp.server": "mmcp.presentation.mcp.server",
    "mmcp.cli": "mmcp.presentation.cli.cli",
}


def _register_legacy_aliases() -> None:
    for legacy_name, canonical_name in _LEGACY_MODULE_ALIASES.items():
        if legacy_name in sys.modules:
            continue
        sys.modules[legacy_name] = importlib.import_module(canonical_name)


_register_legacy_aliases()
