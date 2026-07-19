"""Knowledge manager for unified knowledge base access.

Coordinates between static knowledge documents and dynamic case storage,
providing a single interface for agents to retrieve relevant information.
"""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

from jirin.knowledge.vector_store import VectorStore
from jirin.knowledge.case_store import CaseStore


class KnowledgeManager:
    """Unified knowledge base manager.

    Manages:
    - Static knowledge: Built-in markdown documents about Android stability
    - Dynamic knowledge: Learned cases from past analyses
    - Provides search interfaces for both types
    """

    STATIC_COLLECTION = "static_knowledge"
    CASES_COLLECTION = "case_embeddings"

    def __init__(
        self,
        static_dir: str = "src/jirin/knowledge/static",
        vector_store: VectorStore | None = None,
        case_store: CaseStore | None = None,
    ) -> None:
        self._static_dir = Path(static_dir)
        self._vector_store = vector_store
        self._case_store = case_store
        self._static_loaded = False

    def ensure_static_loaded(self) -> None:
        """Load static knowledge documents into vector store if not already done."""
        if self._static_loaded or self._vector_store is None:
            return

        if not self._static_dir.exists():
            return

        # Check if already loaded
        count = self._vector_store.get_collection_count(self.STATIC_COLLECTION)
        if count > 0:
            self._static_loaded = True
            return

        # Load all markdown files
        for md_file in self._static_dir.rglob("*.md"):
            content = md_file.read_text(encoding="utf-8")
            if not content.strip():
                continue

            # Split into chunks (by sections)
            chunks = self._split_into_chunks(content, max_chunk_size=1000)

            for i, chunk in enumerate(chunks):
                # Use relative path to avoid doc_id collisions across subdirectories
                rel_path = md_file.relative_to(self._static_dir)
                doc_id = f"{rel_path.parent.name}_{rel_path.stem}_{i}" if rel_path.parent.name != "." else f"{rel_path.stem}_{i}"
                metadata = {
                    "source": str(rel_path),
                    "category": md_file.stem,
                    "chunk_index": i,
                }
                self._vector_store.add_documents(
                    collection_name=self.STATIC_COLLECTION,
                    documents=[chunk],
                    ids=[doc_id],
                    metadatas=[metadata],
                )

        self._static_loaded = True

    def _split_into_chunks(
        self, text: str, max_chunk_size: int = 1000
    ) -> list[str]:
        """Split text into chunks by markdown headers or size.

        Args:
            text: Text to split.
            max_chunk_size: Maximum chunk size in characters.

        Returns:
            List of text chunks.
        """
        chunks: list[str] = []
        current_chunk = ""

        for line in text.split("\n"):
            # Start new chunk on headers
            if line.startswith("#") and current_chunk:
                chunks.append(current_chunk.strip())
                current_chunk = line + "\n"
            else:
                current_chunk += line + "\n"

            # Force split if too large
            if len(current_chunk) >= max_chunk_size:
                chunks.append(current_chunk.strip())
                current_chunk = ""

        if current_chunk.strip():
            chunks.append(current_chunk.strip())

        return chunks if chunks else [text[:max_chunk_size]]

    def search_static_knowledge(
        self,
        query: str,
        top_k: int = 3,
    ) -> list[str]:
        """Search static knowledge documents.

        Args:
            query: Search query.
            top_k: Number of results.

        Returns:
            List of relevant knowledge snippets.
        """
        if self._vector_store is None:
            return []

        self.ensure_static_loaded()

        results = self._vector_store.search(
            collection_name=self.STATIC_COLLECTION,
            query=query,
            top_k=top_k,
        )

        return [r["document"] for r in results]

    def search_similar_cases(
        self,
        query: str,
        issue_type: str | None = None,
        top_k: int = 3,
    ) -> list[dict[str, Any]]:
        """Search for similar historical cases.

        First tries vector search, falls back to keyword search.

        Args:
            query: Search query (usually log excerpt).
            issue_type: Filter by issue type.
            top_k: Number of results.

        Returns:
            List of similar cases.
        """
        # Try vector search first
        if self._vector_store is not None:
            results = self._vector_store.search(
                collection_name=self.CASES_COLLECTION,
                query=query[:500],  # Use first 500 chars for embedding
                top_k=top_k,
            )

            cases = []
            for r in results:
                case_id = r.get("metadata", {}).get("case_id")
                if case_id and self._case_store:
                    case = self._case_store.load_case(case_id)
                    if case:
                        case["similarity"] = r.get("similarity", 0)
                        cases.append(case)

            if cases:
                return cases

        # Fallback to keyword search
        if self._case_store:
            return self._case_store.search_cases(
                query=query[:200],
                issue_type=issue_type,
                limit=top_k,
            )

        return []

    def store_case_embedding(self, case_id: str, case_data: dict[str, Any]) -> None:
        """Store case embedding for future similarity search.

        Args:
            case_id: Case identifier.
            case_data: Case data to embed.
        """
        if self._vector_store is None:
            return

        # Build embedding text from case key fields
        parts = []
        if case_data.get("issue_type"):
            parts.append(f"Type: {case_data['issue_type']}")
        if case_data.get("root_cause"):
            parts.append(f"Root Cause: {case_data['root_cause']}")
        if case_data.get("analysis_summary"):
            parts.append(f"Analysis: {case_data['analysis_summary']}")
        if case_data.get("log_excerpt"):
            parts.append(f"Log: {case_data['log_excerpt'][:500]}")

        if not parts:
            return

        embedding_text = "\n".join(parts)
        metadata = {
            "case_id": case_id,
            "issue_type": case_data.get("issue_type", "unknown"),
        }

        self._vector_store.add_documents(
            collection_name=self.CASES_COLLECTION,
            documents=[embedding_text],
            ids=[f"case_{case_id}"],
            metadatas=[metadata],
        )

    def get_knowledge_summary(self) -> dict[str, Any]:
        """Get summary of knowledge base contents.

        Returns:
            Summary statistics.
        """
        summary: dict[str, Any] = {
            "static_docs": 0,
            "cases": 0,
        }

        if self._vector_store:
            summary["static_docs"] = self._vector_store.get_collection_count(
                self.STATIC_COLLECTION
            )
            summary["case_embeddings"] = self._vector_store.get_collection_count(
                self.CASES_COLLECTION
            )

        if self._case_store:
            summary["cases"] = self._case_store.get_stats()

        return summary
