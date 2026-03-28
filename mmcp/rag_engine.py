"""
RAG Engine Module — Context-Life (CL)

Local Retrieval-Augmented Generation using:
  - LanceDB as the vector database (serverless, file-based)
  - sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2 for embeddings

Zero external API calls — everything runs on CPU locally.

RFC Improvements Applied:
  - P3: Real deduplication by file_hash — skips re-indexing unchanged files
  - P4: max_tokens budget for RAG results — truncates to fit token limit
  - P6: Stricter retrieval — min_score filter, per-source dedup, max_chunks_per_source
"""

from __future__ import annotations

import hashlib
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import lancedb
from lancedb.embeddings import get_registry
from lancedb.pydantic import LanceModel, Vector

from mmcp.token_counter import count_tokens, DEFAULT_ENCODING

# --- Configuration ---
DEFAULT_DB_PATH = os.path.expanduser("~/.mmcp/lancedb")
DEFAULT_TABLE_NAME = "knowledge"
DEFAULT_EMBEDDING_MODEL = "paraphrase-multilingual-MiniLM-L12-v2"
DEFAULT_CHUNK_SIZE = 512
DEFAULT_CHUNK_OVERLAP = 64
DEFAULT_TOP_K = 5
DEFAULT_MIN_SCORE = 0.0  # P6: 0.0 = no filter; cosine distance: lower = better
DEFAULT_MAX_CHUNKS_PER_SOURCE = 0  # P6: 0 = no limit


def _get_embedding_function(model_name: str = DEFAULT_EMBEDDING_MODEL):
    """
    Get a sentence-transformers embedding function from LanceDB registry.
    This runs entirely locally on CPU — no API calls.
    """
    registry = get_registry()
    return registry.get("sentence-transformers").create(name=model_name)


# --- Chunking ---

def _chunk_text(
    text: str,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    chunk_overlap: int = DEFAULT_CHUNK_OVERLAP,
) -> list[str]:
    """
    Split text into overlapping chunks of approximately `chunk_size` characters.

    Uses sentence boundaries when possible to avoid cutting mid-thought.
    Falls back to character-level splitting for very long sentences.
    """
    # Split on sentence boundaries
    sentences = re.split(r"(?<=[.!?])\s+", text.strip())

    chunks: list[str] = []
    current_chunk: list[str] = []
    current_length = 0

    for sentence in sentences:
        sentence = sentence.strip()
        if not sentence:
            continue

        sentence_length = len(sentence)

        # If a single sentence exceeds chunk_size, split it by characters
        if sentence_length > chunk_size:
            # Flush current chunk first
            if current_chunk:
                chunks.append(" ".join(current_chunk))
                current_chunk = []
                current_length = 0

            # Character-level split
            for i in range(0, sentence_length, chunk_size - chunk_overlap):
                chunks.append(sentence[i : i + chunk_size])
            continue

        if current_length + sentence_length > chunk_size and current_chunk:
            chunks.append(" ".join(current_chunk))

            # Keep overlap: retain last sentences that fit in overlap window
            overlap_chunk: list[str] = []
            overlap_length = 0
            for s in reversed(current_chunk):
                if overlap_length + len(s) <= chunk_overlap:
                    overlap_chunk.insert(0, s)
                    overlap_length += len(s)
                else:
                    break
            current_chunk = overlap_chunk
            current_length = overlap_length

        current_chunk.append(sentence)
        current_length += sentence_length

    # Final chunk
    if current_chunk:
        chunks.append(" ".join(current_chunk))

    return [c for c in chunks if c.strip()]


def _compute_file_hash(filepath: str) -> str:
    """Compute SHA-256 hash of a file for deduplication."""
    sha256 = hashlib.sha256()
    with open(filepath, "rb") as f:
        for block in iter(lambda: f.read(8192), b""):
            sha256.update(block)
    return sha256.hexdigest()


# --- RAG Engine ---

@dataclass
class SearchResult:
    """A single RAG search result."""

    text: str
    source: str
    score: float
    chunk_index: int

    def to_dict(self) -> dict:
        return {
            "text": self.text,
            "source": self.source,
            "score": round(self.score, 4),
            "chunk_index": self.chunk_index,
        }


class RAGEngine:
    """
    Local RAG engine backed by LanceDB + multilingual sentence-transformers.

    Usage:
        engine = RAGEngine()
        engine.index_file("/path/to/docs/architecture.md")
        results = engine.search("How does auth work?", top_k=5)
    """

    def __init__(
        self,
        db_path: str = DEFAULT_DB_PATH,
        table_name: str = DEFAULT_TABLE_NAME,
        embedding_model: str = DEFAULT_EMBEDDING_MODEL,
        chunk_size: int = DEFAULT_CHUNK_SIZE,
        chunk_overlap: int = DEFAULT_CHUNK_OVERLAP,
    ):
        self.db_path = db_path
        self.table_name = table_name
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap

        # Ensure DB directory exists
        Path(db_path).mkdir(parents=True, exist_ok=True)

        # Initialize embedding function
        self._embedding_fn = _get_embedding_function(embedding_model)

        # Define the LanceDB schema dynamically based on embedding dimensions
        ndims = self._embedding_fn.ndims()

        class KnowledgeChunk(LanceModel):
            text: str = self._embedding_fn.SourceField()
            vector: Vector(ndims) = self._embedding_fn.VectorField()  # type: ignore[valid-type]
            source: str
            chunk_index: int
            file_hash: str

        self._schema = KnowledgeChunk
        self._db = lancedb.connect(db_path)
        self._table = None

        # P3: Track indexed file hashes in memory for fast dedup checks
        self._indexed_hashes: set[str] = set()
        self._load_existing_hashes()

    def _get_or_create_table(self):
        """Lazily get or create the knowledge table."""
        if self._table is not None:
            return self._table

        try:
            self._table = self._db.open_table(self.table_name)
        except Exception:
            self._table = self._db.create_table(
                self.table_name,
                schema=self._schema,
                exist_ok=True,
            )
        return self._table

    def _load_existing_hashes(self) -> None:
        """
        P3: Load existing file hashes from DB into memory set.
        This avoids re-indexing files that haven't changed.
        """
        try:
            table = self._get_or_create_table()
            df = table.to_pandas()
            if "file_hash" in df.columns:
                self._indexed_hashes = set(df["file_hash"].unique())
        except Exception:
            self._indexed_hashes = set()

    def _is_hash_indexed(self, file_hash: str) -> bool:
        """P3: Check if a file hash is already indexed."""
        return file_hash in self._indexed_hashes

    def _remove_by_hash(self, file_hash: str) -> int:
        """
        P3: Remove all chunks with a given file_hash.
        Used when re-indexing a modified file.
        Returns the number of rows deleted.
        """
        try:
            table = self._get_or_create_table()
            # Count before
            before = table.count_rows()
            table.delete(f"file_hash = '{file_hash}'")
            after = table.count_rows()
            self._indexed_hashes.discard(file_hash)
            return before - after
        except Exception:
            return 0

    def index_file(
        self,
        filepath: str,
        source_label: Optional[str] = None,
        force: bool = False,
    ) -> dict:
        """
        Index a text file into the vector database.

        P3: Deduplicates by file hash. If the file hasn't changed,
        it's skipped unless force=True (which re-indexes after
        deleting old chunks).

        Args:
            filepath: Path to the file
            source_label: Optional human-readable label
            force: If True, re-index even if hash matches

        Returns:
            Indexing statistics
        """
        filepath = os.path.abspath(filepath)
        if not os.path.isfile(filepath):
            raise FileNotFoundError(f"File not found: {filepath}")

        file_hash = _compute_file_hash(filepath)
        source = source_label or os.path.basename(filepath)

        # P3: Skip if already indexed and not forced
        if self._is_hash_indexed(file_hash) and not force:
            return {
                "status": "skipped",
                "reason": "already indexed (same hash)",
                "source": source,
                "file_hash": file_hash[:12],
            }

        # P3: If force re-index, remove old chunks first
        if force and self._is_hash_indexed(file_hash):
            removed = self._remove_by_hash(file_hash)

        # Read file content
        with open(filepath, "r", encoding="utf-8", errors="replace") as f:
            content = f.read()

        if not content.strip():
            return {"status": "skipped", "reason": "empty file", "source": source}

        # Chunk the content
        chunks = _chunk_text(content, self.chunk_size, self.chunk_overlap)

        if not chunks:
            return {"status": "skipped", "reason": "no chunks generated", "source": source}

        # Prepare records
        records = [
            {
                "text": chunk,
                "source": source,
                "chunk_index": i,
                "file_hash": file_hash,
            }
            for i, chunk in enumerate(chunks)
        ]

        # Add to LanceDB (the embedding function handles vectorization automatically)
        table = self._get_or_create_table()
        table.add(records)

        # P3: Track the hash
        self._indexed_hashes.add(file_hash)

        return {
            "status": "indexed",
            "source": source,
            "chunks": len(chunks),
            "file_hash": file_hash[:12],
        }

    def index_directory(
        self,
        dirpath: str,
        extensions: Optional[list[str]] = None,
        recursive: bool = True,
        force: bool = False,
    ) -> dict:
        """
        Index all matching files in a directory.

        Args:
            dirpath: Path to the directory
            extensions: File extensions to include (e.g. [".md", ".py", ".txt"])
                        Defaults to common text/code files.
            recursive: Whether to recurse into subdirectories
            force: P3 — force re-index even if files haven't changed
        """
        if extensions is None:
            extensions = [
                ".md", ".txt", ".py", ".js", ".ts", ".go",
                ".rs", ".java", ".yaml", ".yml", ".toml",
                ".json", ".html", ".css", ".sh",
            ]

        dirpath = os.path.abspath(dirpath)
        if not os.path.isdir(dirpath):
            raise NotADirectoryError(f"Not a directory: {dirpath}")

        results = {"indexed": 0, "skipped": 0, "errors": 0, "files": []}

        pattern = "**/*" if recursive else "*"
        for ext in extensions:
            for filepath in Path(dirpath).glob(f"{pattern}{ext}"):
                try:
                    result = self.index_file(str(filepath), force=force)
                    if result["status"] == "indexed":
                        results["indexed"] += 1
                    else:
                        results["skipped"] += 1
                    results["files"].append(result)
                except Exception as e:
                    results["errors"] += 1
                    results["files"].append({
                        "status": "error",
                        "source": str(filepath),
                        "error": str(e),
                    })

        return results

    def search(
        self,
        query: str,
        top_k: int = DEFAULT_TOP_K,
        max_tokens: int = 0,
        min_score: float = DEFAULT_MIN_SCORE,
        max_chunks_per_source: int = DEFAULT_MAX_CHUNKS_PER_SOURCE,
        encoding: str = DEFAULT_ENCODING,
    ) -> list[SearchResult]:
        """
        Perform semantic search over the indexed knowledge base.

        P4: max_tokens — If > 0, truncates results so total text
            fits within the token budget. Prevents RAG from flooding
            the context window.
        P6: min_score — Filter out results above this distance threshold
            (cosine distance: lower = more similar, so higher = worse).
        P6: max_chunks_per_source — Limit chunks per source file
            to avoid one file dominating the RAG context.

        Args:
            query: Natural language search query
            top_k: Max results to retrieve from vector DB
            max_tokens: Token budget ceiling for results (0 = no limit)
            min_score: Max cosine distance to accept (0.0 = accept all)
            max_chunks_per_source: Max chunks per source (0 = no limit)
            encoding: Tiktoken encoding for token counting

        Returns:
            List of filtered, budget-aware SearchResults
        """
        table = self._get_or_create_table()

        try:
            results = (
                table.search(query)
                .metric("cosine")
                .limit(top_k)
                .to_pandas()
            )
        except Exception:
            return []

        search_results: list[SearchResult] = []
        source_counts: dict[str, int] = {}  # P6: track per-source chunks
        running_tokens = 0  # P4: track token consumption

        for _, row in results.iterrows():
            text = row.get("text", "")
            source = row.get("source", "unknown")
            score = float(row.get("_distance", 0.0))
            chunk_index = int(row.get("chunk_index", 0))

            # P6: Filter by minimum score (cosine distance threshold)
            if min_score > 0 and score > min_score:
                continue

            # P6: Enforce max chunks per source
            if max_chunks_per_source > 0:
                current_count = source_counts.get(source, 0)
                if current_count >= max_chunks_per_source:
                    continue
                source_counts[source] = current_count + 1

            # P4: Check token budget before adding
            if max_tokens > 0:
                chunk_tokens = count_tokens(text, encoding)
                if running_tokens + chunk_tokens > max_tokens:
                    break  # Stop — we've hit the budget
                running_tokens += chunk_tokens

            search_results.append(
                SearchResult(
                    text=text,
                    source=source,
                    score=score,
                    chunk_index=chunk_index,
                )
            )

        return search_results

    def clear(self) -> dict:
        """Drop the knowledge table and recreate it empty."""
        try:
            self._db.drop_table(self.table_name)
        except Exception:
            pass
        self._table = None
        self._indexed_hashes.clear()
        return {"status": "cleared", "table": self.table_name}

    def stats(self) -> dict:
        """Get statistics about the indexed knowledge base."""
        try:
            table = self._get_or_create_table()
            count = table.count_rows()
            return {
                "table": self.table_name,
                "total_chunks": count,
                "unique_files": len(self._indexed_hashes),
                "db_path": self.db_path,
            }
        except Exception as e:
            return {"table": self.table_name, "total_chunks": 0, "error": str(e)}
