from __future__ import annotations

from mmcp.application.ports.knowledge_store import KnowledgeStorePort
from mmcp.infrastructure.knowledge.rag_engine import RAGEngine


class RAGEngineKnowledgeStoreAdapter(KnowledgeStorePort):
    def __init__(self, engine: RAGEngine):
        self.engine = engine

    @property
    def db_path(self) -> str:
        return self.engine.db_path

    @property
    def table_name(self) -> str:
        return self.engine.table_name

    @property
    def chunk_size(self) -> int:
        return self.engine.chunk_size

    @property
    def chunk_overlap(self) -> int:
        return self.engine.chunk_overlap

    def index_file(self, filepath: str, source_label: str | None = None, force: bool = False) -> dict:
        return self.engine.index_file(filepath, source_label=source_label, force=force)

    def index_directory(
        self,
        dirpath: str,
        extensions: list[str] | None = None,
        recursive: bool = True,
        force: bool = False,
    ) -> dict:
        return self.engine.index_directory(dirpath, extensions=extensions, recursive=recursive, force=force)

    def search(
        self,
        query: str,
        top_k: int = 5,
        max_tokens: int = 0,
        min_score: float = 0.0,
        max_chunks_per_source: int = 0,
    ) -> list[object]:
        return self.engine.search(
            query,
            top_k=top_k,
            max_tokens=max_tokens,
            min_score=min_score,
            max_chunks_per_source=max_chunks_per_source,
        )

    def prewarm(self) -> None:
        self.engine.prewarm()

    def stats(self) -> dict:
        return self.engine.stats()

    def clear(self) -> dict:
        return self.engine.clear()

    def is_model_loaded(self) -> bool:
        loaded = getattr(self.engine, "is_model_loaded", None)
        if callable(loaded):
            return bool(loaded())
        return bool(getattr(self.engine, "_model_loaded", False))
