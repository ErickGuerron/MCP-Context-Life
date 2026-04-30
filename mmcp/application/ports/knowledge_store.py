from __future__ import annotations

from typing import Protocol


class KnowledgeStorePort(Protocol):
    def index_file(self, filepath: str, source_label: str | None = None, force: bool = False) -> dict: ...

    def index_directory(
        self,
        dirpath: str,
        extensions: list[str] | None = None,
        recursive: bool = True,
        force: bool = False,
    ) -> dict: ...

    def search(
        self,
        query: str,
        top_k: int = 5,
        max_tokens: int = 0,
        min_score: float = 0.0,
        max_chunks_per_source: int = 0,
    ) -> list[object]: ...

    def prewarm(self) -> None: ...

    def stats(self) -> dict: ...

    def clear(self) -> dict: ...

    def is_model_loaded(self) -> bool: ...
