from __future__ import annotations

import os
from dataclasses import dataclass

from mmcp.application.ports.knowledge_store import KnowledgeStorePort
from mmcp.infrastructure.environment.config import get_config


@dataclass
class KnowledgeService:
    store: KnowledgeStorePort

    def index_knowledge(self, path: str, recursive: bool = True, force: bool = False) -> dict:
        if os.path.isfile(path):
            return self.store.index_file(path, force=force)
        if os.path.isdir(path):
            return self.store.index_directory(path, recursive=recursive, force=force)
        return {"status": "error", "error": f"Path not found: {path}"}

    def search_context(
        self,
        query: str,
        top_k: int = 5,
        max_tokens: int = 0,
        min_score: float = 0.0,
        max_chunks_per_source: int = 0,
    ) -> dict:
        results = self.store.search(
            query,
            top_k=top_k,
            max_tokens=max_tokens,
            min_score=min_score,
            max_chunks_per_source=max_chunks_per_source,
        )
        return {
            "query": query,
            "results_count": len(results),
            "results": [result.to_dict() for result in results],
        }

    def prewarm_rag_now(self) -> dict:
        already_loaded = self.store.is_model_loaded()
        if not already_loaded:
            self.store.prewarm()

        return {
            "status": "ready",
            "mode": get_config().rag_warmup_mode,
            "already_loaded": already_loaded,
            "model_loaded": self.store.is_model_loaded(),
            "message": "RAG embedding model is warm and ready for the next MCP search/index call.",
        }

    def rag_stats(self) -> dict:
        return self.store.stats()

    def clear_knowledge(self) -> dict:
        return self.store.clear()
