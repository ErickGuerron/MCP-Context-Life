"""
Application container for Context-Life (CL).

Owns the shared runtime objects behind the MCP server so the server module
can stay focused on composition and routing.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from mcp.server.fastmcp import FastMCP

from mmcp.application.features.context.service import ContextService
from mmcp.application.features.knowledge.adapters import RAGEngineKnowledgeStoreAdapter
from mmcp.application.features.knowledge.service import KnowledgeService
from mmcp.application.features.telemetry.service import TelemetryService
from mmcp.application.features.tokens.adapters import TokenCounterAdapter
from mmcp.application.features.tokens.service import TokenBudgetService
from mmcp.infrastructure.environment.config import get_config, get_rag_warmup_mode_details
from mmcp.infrastructure.knowledge.rag_engine import RAGEngine
from mmcp.infrastructure.persistence.cache_manager import CacheLoop
from mmcp.infrastructure.persistence.session_store import SessionStore
from mmcp.infrastructure.tokens.token_counter import TokenBudget


def _build_mcp() -> FastMCP:
    return FastMCP(
        "Context-Life",
        instructions=(
            "Context-Life (CL) â€” LLM context optimization server. "
            "Use these tools to count tokens, trim message history, "
            "search indexed knowledge via RAG, and optimize context caching."
        ),
    )


@dataclass
class AppContainer:
    """Shared runtime container for MCP tools and resources."""

    mcp: FastMCP = field(default_factory=_build_mcp)
    _token_budget: Optional[TokenBudget] = field(default=None, init=False, repr=False)
    _tokens_service: Optional[TokenBudgetService] = field(default=None, init=False, repr=False)
    _cache_loop: Optional[CacheLoop] = field(default=None, init=False, repr=False)
    _context_service: Optional[ContextService] = field(default=None, init=False, repr=False)
    _knowledge_service: Optional[KnowledgeService] = field(default=None, init=False, repr=False)
    _telemetry_service: Optional[TelemetryService] = field(default=None, init=False, repr=False)
    _rag_engine: Optional[RAGEngine] = field(default=None, init=False, repr=False)
    _runtime_initialized: bool = field(default=False, init=False, repr=False)
    _token_budget_config_key: Optional[tuple[int, int]] = field(default=None, init=False, repr=False)
    _rag_engine_config_key: Optional[tuple[str, str, int, int]] = field(default=None, init=False, repr=False)
    _cache_loop_config_key: Optional[tuple[int, int, int, str]] = field(default=None, init=False, repr=False)
    _context_service_config_key: Optional[tuple[int, int, int, str]] = field(default=None, init=False, repr=False)
    _knowledge_service_config_key: Optional[tuple[str, str, int, int]] = field(default=None, init=False, repr=False)
    _telemetry_service_config_key: Optional[str] = field(default=None, init=False, repr=False)
    _runtime_initialized_key: Optional[tuple[str, tuple[str, str, int, int]]] = field(
        default=None, init=False, repr=False
    )

    def _current_token_budget_config_key(self) -> tuple[int, int]:
        cfg = get_config()
        return (cfg.token_budget_default, cfg.token_budget_safety_buffer)

    def _current_rag_engine_config_key(self) -> tuple[str, str, int, int]:
        cfg = get_config()
        return (
            cfg.resolve_rag_db_path(),
            cfg.rag_table_name,
            cfg.rag_chunk_size,
            cfg.rag_chunk_overlap,
        )

    def _current_cache_loop_config_key(self) -> tuple[int, int, int, str]:
        cfg = get_config()
        return (
            cfg.cache_max_entries,
            cfg.cache_rag_thrash_threshold,
            cfg.cache_rag_bypass_cooldown,
            str(cfg.resolve_cache_db_path()),
        )

    def get_token_budget(self) -> TokenBudget:
        return self.get_tokens_service().budget

    def get_tokens_service(self) -> TokenBudgetService:
        current_key = self._current_token_budget_config_key()
        if self._tokens_service is None or self._token_budget_config_key != current_key:
            cfg = get_config()
            self._tokens_service = TokenBudgetService(
                TokenCounterAdapter(),
                budget=TokenBudget(
                    max_tokens=cfg.token_budget_default,
                    safety_buffer=cfg.token_budget_safety_buffer / 10000.0,
                ),
            )
            self._token_budget_config_key = current_key
            self._token_budget = self._tokens_service.budget
        return self._tokens_service

    def get_cache_loop(self) -> CacheLoop:
        current_key = self._current_cache_loop_config_key()
        if self._cache_loop is None or self._cache_loop_config_key != current_key:
            self._cache_loop = CacheLoop()
            self._cache_loop_config_key = current_key
        return self._cache_loop

    def get_context_service(self) -> ContextService:
        current_key = self._current_cache_loop_config_key()
        if self._context_service is None or self._context_service_config_key != current_key:
            self._context_service = ContextService(self.get_cache_loop())
            self._context_service_config_key = current_key
        return self._context_service

    def get_knowledge_service(self) -> KnowledgeService:
        current_key = self._current_rag_engine_config_key()
        if self._knowledge_service is None or self._knowledge_service_config_key != current_key:
            self._knowledge_service = KnowledgeService(RAGEngineKnowledgeStoreAdapter(self.get_rag_engine()))
            self._knowledge_service_config_key = current_key
        return self._knowledge_service

    def get_telemetry_service(self) -> TelemetryService:
        current_key = str(get_config().resolve_cache_db_path())
        if self._telemetry_service is None or self._telemetry_service_config_key != current_key:
            self._telemetry_service = TelemetryService(SessionStore(Path(current_key)))
            self._telemetry_service_config_key = current_key
        return self._telemetry_service

    def get_rag_engine(self) -> RAGEngine:
        current_key = self._current_rag_engine_config_key()
        if self._rag_engine is None or self._rag_engine_config_key != current_key:
            cfg = get_config()
            self._rag_engine = RAGEngine(
                db_path=cfg.resolve_rag_db_path(),
                table_name=cfg.rag_table_name,
                chunk_size=cfg.rag_chunk_size,
                chunk_overlap=cfg.rag_chunk_overlap,
            )
            self._rag_engine_config_key = current_key
        return self._rag_engine

    def initialize_runtime(self, force: bool = False) -> dict:
        """Apply configured startup behavior for RAG warmup."""
        cfg = get_config()
        mode = cfg.rag_warmup_mode
        details = get_rag_warmup_mode_details(mode)
        runtime_key = (mode, self._current_rag_engine_config_key())

        if self._runtime_initialized and self._runtime_initialized_key == runtime_key and not force:
            return {
                "status": "already_initialized",
                "mode": mode,
                "prewarmed": self._rag_engine is not None and self._rag_engine._model_loaded,
                "mcp_impact": details["current"]["mcp_impact"],
            }

        prewarmed = False
        if mode == "startup":
            engine = self.get_rag_engine()
            if not engine._model_loaded:
                engine.prewarm()
            prewarmed = engine._model_loaded

        self._runtime_initialized = True
        self._runtime_initialized_key = runtime_key
        return {
            "status": "initialized",
            "mode": mode,
            "prewarmed": prewarmed,
            "mcp_impact": details["current"]["mcp_impact"],
        }

    def prewarm_rag_now(self) -> dict:
        """Explicitly prewarm the RAG model on demand."""
        return self.get_knowledge_service().prewarm_rag_now()

    def set_token_budget(self, max_tokens: int, safety_buffer: float) -> TokenBudget:
        self._token_budget = TokenBudget(max_tokens=max_tokens, safety_buffer=safety_buffer)
        if self._tokens_service is None:
            self._tokens_service = TokenBudgetService(TokenCounterAdapter(), budget=self._token_budget)
        else:
            self._tokens_service.budget = self._token_budget
        self._token_budget_config_key = self._current_token_budget_config_key()
        return self._token_budget

    def get_rag_warmup_status(self) -> dict:
        details = get_rag_warmup_mode_details(get_config().rag_warmup_mode)
        return {
            "current_mode": details["current_mode"],
            "current": details["current"],
            "modes": details["modes"],
            "engine_initialized": self._rag_engine is not None,
            "model_loaded": self._rag_engine._model_loaded if self._rag_engine is not None else False,
        }

    def reset_runtime_state(self) -> None:
        self._rag_engine = None
        self._runtime_initialized = False
        self._token_budget = None
        self._tokens_service = None
        self._cache_loop = None
        self._context_service = None
        self._knowledge_service = None
        self._telemetry_service = None
        self._token_budget_config_key = None
        self._rag_engine_config_key = None
        self._cache_loop_config_key = None
        self._context_service_config_key = None
        self._knowledge_service_config_key = None
        self._telemetry_service_config_key = None
        self._runtime_initialized_key = None

